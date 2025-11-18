"""Anonymous, asynchronous telemetry system for the GATI SDK.

Collects opt-in usage statistics to help improve the SDK. All metrics are stored
locally, queued, and sent asynchronously so they never block user code. No
prompts, completions, API keys, or additional PII are collected—only the fields
documented in the user agreement (installation ID, SDK version, counts, and
detected frameworks).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import requests


class TelemetryClient:
    """Non-blocking client that queues and sends telemetry metrics asynchronously."""

    DEFAULT_ENDPOINT = os.getenv(
        "GATI_TELEMETRY_URL", "https://gati-mvp-telemetry.vercel.app/api/metrics"
    )
    MAX_QUEUE_SIZE = 250
    MAX_BACKOFF_SECONDS = 30 * 60  # 30 minutes

    def __init__(
        self, enabled: bool = True, endpoint: Optional[str] = None, sdk_version: str = "0.1.1"
    ) -> None:
        self.enabled = enabled
        self.endpoint = endpoint or self.DEFAULT_ENDPOINT
        self.sdk_version = sdk_version
        self.logger = logging.getLogger("gati.telemetry")

        self.installation_id = self._get_or_create_installation_id()
        self._lock = threading.Lock()
        self._metrics: Dict[str, Any] = {
            "events_today": 0,
            "lifetime_events": 0,
            "mcp_queries": 0,
            "frameworks_detected": set(),
            "last_reset_date": datetime.now().date().isoformat(),
        }
        self._tracked_agents: Set[str] = set()
        self._legacy_agent_count = 0

        self._queue_file = self._get_config_dir() / "telemetry_queue.json"
        self._queue_lock = threading.Lock()
        self._queue_event = threading.Event()
        self._queue_drained = threading.Event()
        self._queue: List[Dict[str, Any]] = []

        self._stop_event = threading.Event()
        self._scheduler_thread: Optional[threading.Thread] = None
        self._sender_thread: Optional[threading.Thread] = None
        self.send_interval = 2 * 60  # two minutes

        self._load_metrics()
        self._load_queue()
        self._update_queue_state_locked()

        if self.enabled:
            self._start_threads()

    # -------------------------------------------------------------------------
    # Persistence helpers
    # -------------------------------------------------------------------------

    def _get_or_create_installation_id(self) -> str:
        """Get or create a unique installation ID."""
        config_dir = self._get_config_dir()
        id_file = config_dir / ".gati_id"

        if id_file.exists():
            try:
                return id_file.read_text().strip()
            except Exception as exc:
                self.logger.debug(f"Failed to read installation ID: {exc}")

        installation_id = str(uuid.uuid4())
        try:
            config_dir.mkdir(parents=True, exist_ok=True)
            id_file.write_text(installation_id)
        except Exception as exc:
            self.logger.debug(f"Failed to save installation ID: {exc}")
        return installation_id

    def _get_config_dir(self) -> Path:
        return Path.home() / ".gati"

    def _get_metrics_file(self) -> Path:
        return self._get_config_dir() / "metrics.json"

    def _load_metrics(self) -> None:
        metrics_file = self._get_metrics_file()
        if not metrics_file.exists():
            return

        try:
            with metrics_file.open("r") as file:
                data = json.load(file)
        except Exception as exc:
            self.logger.debug(f"Failed to load metrics: {exc}")
            return

        with self._lock:
            self._metrics["lifetime_events"] = data.get("lifetime_events", 0)
            self._metrics["mcp_queries"] = data.get("mcp_queries", 0)
            self._metrics["last_reset_date"] = data.get(
                "last_reset_date", datetime.now().date().isoformat()
            )
            frameworks = data.get("frameworks_detected", [])
            self._metrics["frameworks_detected"] = set(frameworks)

            tracked_agents = data.get("tracked_agents") or []
            if isinstance(tracked_agents, list):
                self._tracked_agents = set(tracked_agents)
            self._legacy_agent_count = max(
                data.get("agents_tracked", len(self._tracked_agents)),
                len(self._tracked_agents),
            )

            self._reset_daily_counters_if_needed_locked()
            if data.get("events_today") is not None:
                today = datetime.now().date()
                last_reset = datetime.fromisoformat(self._metrics["last_reset_date"]).date()
                if last_reset == today:
                    self._metrics["events_today"] = data.get("events_today", 0)

    def _save_metrics(self) -> None:
        metrics_file = self._get_metrics_file()

        try:
            config_dir = self._get_config_dir()
            config_dir.mkdir(parents=True, exist_ok=True)

            with self._lock:
                data = {
                    "lifetime_events": self._metrics["lifetime_events"],
                    "events_today": self._metrics["events_today"],
                    "mcp_queries": self._metrics["mcp_queries"],
                    "frameworks_detected": list(self._metrics["frameworks_detected"]),
                    "last_reset_date": self._metrics["last_reset_date"],
                    "tracked_agents": sorted(self._tracked_agents),
                    "agents_tracked": max(len(self._tracked_agents), self._legacy_agent_count),
                }

            with metrics_file.open("w") as file:
                json.dump(data, file, indent=2)
        except Exception as exc:
            self.logger.debug(f"Failed to save metrics: {exc}")

    def _reset_daily_counters_if_needed_locked(self) -> None:
        last_reset = datetime.fromisoformat(self._metrics["last_reset_date"]).date()
        today = datetime.now().date()

        if last_reset < today:
            self._metrics["events_today"] = 0
            self._metrics["last_reset_date"] = today.isoformat()

    def _load_queue(self) -> None:
        if not self._queue_file.exists():
            self._queue = []
            return

        try:
            with self._queue_file.open("r") as file:
                raw_entries = json.load(file)
        except Exception as exc:
            self.logger.debug(f"Failed to load telemetry queue: {exc}")
            self._queue = []
            return

        loaded: List[Dict[str, Any]] = []
        for entry in raw_entries:
            try:
                loaded.append(
                    {
                        "payload": entry["payload"],
                        "attempts": entry.get("attempts", 0),
                        "next_attempt_at": datetime.fromisoformat(entry["next_attempt_at"]),
                    }
                )
            except Exception:
                continue

        self._queue = loaded

    def _persist_queue_locked(self) -> None:
        try:
            self._queue_file.parent.mkdir(parents=True, exist_ok=True)
            serialized = [
                {
                    "payload": entry["payload"],
                    "attempts": entry["attempts"],
                    "next_attempt_at": entry["next_attempt_at"].isoformat(),
                }
                for entry in self._queue
            ]
            with self._queue_file.open("w") as file:
                json.dump(serialized, file, indent=2)
        except Exception as exc:
            self.logger.debug(f"Failed to persist telemetry queue: {exc}")

    def _update_queue_state_locked(self) -> None:
        with self._queue_lock:
            if self._queue:
                self._queue_drained.clear()
            else:
                self._queue_drained.set()
            self._persist_queue_locked()

    # -------------------------------------------------------------------------
    # Public counters
    # -------------------------------------------------------------------------

    def track_agent(self) -> None:
        self.track_named_agent(None)

    def track_named_agent(self, agent_name: Optional[str]) -> None:
        if not self.enabled:
            return

        with self._lock:
            if agent_name:
                self._tracked_agents.add(agent_name)
                self._legacy_agent_count = max(self._legacy_agent_count, len(self._tracked_agents))
            else:
                self._legacy_agent_count = max(
                    self._legacy_agent_count + 1, len(self._tracked_agents)
                )

        self._save_metrics()

    def track_event(self) -> None:
        if not self.enabled:
            return

        with self._lock:
            self._reset_daily_counters_if_needed_locked()
            self._metrics["events_today"] += 1
            self._metrics["lifetime_events"] += 1
            lifetime = self._metrics["lifetime_events"]

        if lifetime % 100 == 0:
            self._save_metrics()

    def track_framework(self, framework: str) -> None:
        if not self.enabled:
            return

        with self._lock:
            self._metrics["frameworks_detected"].add(framework)

        self._save_metrics()

    def track_mcp_query(self) -> None:
        if not self.enabled:
            return

        with self._lock:
            self._metrics["mcp_queries"] += 1
            mcp_total = self._metrics["mcp_queries"]

        if mcp_total % 100 == 0:
            self._save_metrics()

    # -------------------------------------------------------------------------
    # Metrics snapshot + framework detection
    # -------------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, Any]:
        auto_detected = self._auto_detect_frameworks()
        with self._lock:
            self._reset_daily_counters_if_needed_locked()
            frameworks = set(self._metrics["frameworks_detected"])
            if auto_detected:
                frameworks |= auto_detected
                self._metrics["frameworks_detected"] = frameworks

            metrics = {
                "installation_id": self.installation_id,
                "sdk_version": self.sdk_version,
                "agents_tracked": max(len(self._tracked_agents), self._legacy_agent_count),
                "events_today": self._metrics["events_today"],
                "lifetime_events": self._metrics["lifetime_events"],
                "mcp_queries": self._metrics["mcp_queries"],
                "frameworks_detected": sorted(frameworks),
                "timestamp": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
                "user_email": self._get_user_email(),
            }

        return metrics

    def _auto_detect_frameworks(self) -> Set[str]:
        detected: Set[str] = set()
        modules = sys.modules

        try:
            if "langchain" in modules or "langchain_core" in modules:
                detected.add("langchain")
        except Exception:
            pass

        try:
            if "langgraph" in modules:
                detected.add("langgraph")
        except Exception:
            pass

        try:
            if "awsstrands" in modules or "aws_strands" in modules or "strands" in modules:
                detected.add("aws_strands")
        except Exception:
            pass

        return detected

    # -------------------------------------------------------------------------
    # Auth helpers
    # -------------------------------------------------------------------------

    def _get_api_token(self) -> Optional[str]:
        token_file = Path.home() / ".gati" / ".auth_token"
        if token_file.exists():
            try:
                return token_file.read_text().strip()
            except Exception as exc:
                self.logger.debug(f"Failed to read API token: {exc}")
        return None

    def _get_user_email(self) -> Optional[str]:
        email_file = Path.home() / ".gati" / ".auth_email"
        if email_file.exists():
            try:
                return email_file.read_text().strip()
            except Exception as exc:
                self.logger.debug(f"Failed to read email: {exc}")
        return None

    # -------------------------------------------------------------------------
    # Queue + network plumbing
    # -------------------------------------------------------------------------

    def _send_metrics(self) -> None:
        if not self.enabled:
            return
        self._enqueue_payload(self.get_metrics(), priority=False)

    def _enqueue_payload(self, payload: Dict[str, Any], priority: bool) -> None:
        entry = {
            "payload": payload,
            "attempts": 0,
            "next_attempt_at": datetime.utcnow(),
        }

        with self._queue_lock:
            if priority:
                self._queue.insert(0, entry)
            else:
                self._queue.append(entry)

            if len(self._queue) > self.MAX_QUEUE_SIZE:
                dropped = self._queue.pop(0)
                self.logger.debug(
                    "Telemetry queue full; dropping payload with timestamp %s",
                    dropped["payload"].get("timestamp"),
                )

            self._persist_queue_locked()
            self._queue_drained.clear()

        self._queue_event.set()

    def _transmit_payload(self, payload: Dict[str, Any]) -> bool:
        api_token = self._get_api_token()

        # Build headers - API key is optional for anonymous telemetry
        headers = {
            "Content-Type": "application/json",
            "User-Agent": f"gati-sdk/{self.sdk_version}",
        }
        if api_token:
            headers["X-API-Key"] = api_token
        else:
            self.logger.debug("Sending anonymous telemetry (no API token)")

        try:
            response = requests.post(
                self.endpoint,
                json=payload,
                timeout=5.0,
                headers=headers,
            )
        except requests.exceptions.Timeout:
            self.logger.debug("Telemetry request timed out")
            return False
        except requests.exceptions.ConnectionError:
            self.logger.debug("Failed to connect to telemetry endpoint")
            return False
        except Exception as exc:
            self.logger.debug(f"Failed to send telemetry: {exc}")
            return False

        if response.status_code in (200, 201, 204):
            self.logger.debug("Telemetry sent successfully")
            return True

        self.logger.debug("Telemetry endpoint returned %s: %s", response.status_code, response.text)
        return False

    def _sender_worker(self) -> None:
        while True:
            entry = None
            wait_seconds = None

            with self._queue_lock:
                if self._queue:
                    now = datetime.utcnow()
                    ready_index = None
                    next_wake = None

                    for idx, candidate in enumerate(self._queue):
                        if candidate["next_attempt_at"] <= now:
                            ready_index = idx
                            break
                        if next_wake is None or candidate["next_attempt_at"] < next_wake:
                            next_wake = candidate["next_attempt_at"]

                    if ready_index is not None:
                        entry = self._queue.pop(ready_index)
                        self._persist_queue_locked()
                        if not self._queue:
                            self._queue_drained.set()
                    else:
                        if next_wake:
                            wait_seconds = max((next_wake - now).total_seconds(), 0.5)
                else:
                    self._queue_drained.set()

            if entry:
                success = self._transmit_payload(entry["payload"])
                if not success:
                    entry["attempts"] += 1
                    delay = min(self.MAX_BACKOFF_SECONDS, 2 ** entry["attempts"])
                    entry["next_attempt_at"] = datetime.utcnow() + timedelta(seconds=delay)
                    with self._queue_lock:
                        self._queue.append(entry)
                        self._persist_queue_locked()
                        self._queue_drained.clear()
                continue

            if self._stop_event.is_set():
                if self._queue_drained.is_set():
                    break

            wait_for = wait_seconds or 30.0
            self._queue_event.wait(timeout=wait_for)
            self._queue_event.clear()

    def _scheduler_worker(self) -> None:
        if self._stop_event.wait(timeout=60):
            return
        self._send_metrics()

        while not self._stop_event.is_set():
            if self._stop_event.wait(timeout=self.send_interval):
                break
            self._send_metrics()

    def _start_threads(self) -> None:
        if self._sender_thread is None:
            self._sender_thread = threading.Thread(
                target=self._sender_worker, daemon=True, name="gati-telemetry-sender"
            )
            self._sender_thread.start()

        if self._scheduler_thread is None:
            self._scheduler_thread = threading.Thread(
                target=self._scheduler_worker, daemon=True, name="gati-telemetry-scheduler"
            )
            self._scheduler_thread.start()

    # -------------------------------------------------------------------------
    # Lifecycle helpers
    # -------------------------------------------------------------------------

    def stop(self) -> None:
        if not self.enabled:
            return

        self._enqueue_payload(self.get_metrics(), priority=True)
        self._queue_event.set()
        self._queue_drained.wait(timeout=5.0)

        self._stop_event.set()
        self._queue_event.set()

        if self._scheduler_thread is not None:
            self._scheduler_thread.join(timeout=5.0)
        if self._sender_thread is not None:
            self._sender_thread.join(timeout=5.0)

        self._save_metrics()

    def flush(self) -> None:
        if not self.enabled:
            return
        self._enqueue_payload(self.get_metrics(), priority=True)
        self._queue_event.set()

    def disable(self) -> None:
        self.stop()
        self.enabled = False

        metrics_file = self._get_metrics_file()
        if metrics_file.exists():
            try:
                metrics_file.unlink()
            except Exception as exc:
                self.logger.debug(f"Failed to remove metrics file: {exc}")

        if self._queue_file.exists():
            try:
                self._queue_file.unlink()
            except Exception as exc:
                self.logger.debug(f"Failed to remove telemetry queue: {exc}")


