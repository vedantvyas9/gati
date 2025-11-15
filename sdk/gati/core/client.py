"""HTTP client for sending events to the backend."""
import time
import threading
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin

import requests

from gati.core.event import Event
from gati.core.config import config


class EventClient:
    """HTTP client for sending events to the backend.
    
    Handles authentication, retry logic, and error handling. Uses threading
    to send events asynchronously without blocking user code.
    """
    
    def __init__(
        self,
        backend_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 10.0,
        max_retries: int = 3,
    ):
        """Initialize event client.

        Args:
            backend_url: Backend server URL (default from config)
            api_key: API key for authentication (default from config)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.backend_url = backend_url or config.backend_url
        self.api_key = api_key or config.api_key
        self.timeout = timeout
        self.max_retries = max_retries

        # Build the events endpoint URL
        self.events_url = urljoin(self.backend_url.rstrip("/") + "/", "api/events")

        # Session for connection pooling
        self._session = requests.Session()

        # Set default headers
        self._session.headers.update({
            "Content-Type": "application/json",
        })

        # Add API key to headers if provided
        if self.api_key:
            self._session.headers.update({
                "Authorization": f"Bearer {self.api_key}",
            })

        # Track active send threads for proper cleanup
        self._active_threads: List[threading.Thread] = []
        self._threads_lock = threading.Lock()
    
    def _prepare_events(self, events: List[Event]) -> List[Dict[str, Any]]:
        """Convert events to dictionaries for JSON serialization.
        
        Args:
            events: List of Event objects
            
        Returns:
            List of event dictionaries
        """
        return [event.to_dict() for event in events]
    
    def _send_with_retry(self, events: List[Dict[str, Any]]) -> bool:
        """Send events with retry logic and exponential backoff.
        
        Args:
            events: List of event dictionaries to send
            
        Returns:
            True if successful, False otherwise
        """
        for attempt in range(self.max_retries + 1):
            try:
                response = self._session.post(
                    self.events_url,
                    json={"events": events},  # Wrap in EventBatch format
                    timeout=self.timeout,
                )
                
                # Check if request was successful
                if response.status_code in (200, 201, 204):
                    return True
                
                # Don't retry on client errors (4xx) except 429 (rate limit)
                if 400 <= response.status_code < 500 and response.status_code != 429:
                    # Log error but don't retry
                    print(f"Client error {response.status_code}: {response.text}")
                    return False
                
                # For server errors (5xx) and 429, retry
                if attempt < self.max_retries:
                    # Exponential backoff: 1s, 2s, 4s
                    wait_time = 2 ** attempt
                    print(f"Server error {response.status_code}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"Server error {response.status_code} after {self.max_retries} retries: {response.text}")
                    return False
                    
            except requests.exceptions.Timeout:
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt
                    print(f"Request timeout, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"Request timeout after {self.max_retries} retries")
                    return False
                    
            except requests.exceptions.ConnectionError as e:
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt
                    print(f"Connection error, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"Connection error after {self.max_retries} retries: {e}")
                    return False
                    
            except Exception as e:
                # Unexpected error - log and don't retry
                print(f"Unexpected error sending events: {e}")
                return False
        
        return False
    
    def send_events(self, events: List[Event]) -> None:
        """Send events to the backend asynchronously.

        This method sends events in a background thread to avoid blocking
        the user's code. Errors are logged but don't raise exceptions.

        Args:
            events: List of Event objects to send
        """
        if not events:
            return

        # Convert events to dictionaries
        events_dict = self._prepare_events(events)

        # Clean up finished threads before starting a new one
        self._cleanup_finished_threads()

        # Send in background thread to avoid blocking
        thread = threading.Thread(
            target=self._send_events_sync,
            args=(events_dict,),
            daemon=True,
        )

        # Track the thread so we can wait for it during flush
        with self._threads_lock:
            self._active_threads.append(thread)

        thread.start()
    
    def _send_events_sync(self, events: List[Dict[str, Any]]) -> None:
        """Synchronous send method (called from background thread).

        Args:
            events: List of event dictionaries to send
        """
        try:
            self._send_with_retry(events)
        except Exception as e:
            # Catch any unexpected errors - don't crash user's code
            print(f"Error sending events: {e}")

    def _cleanup_finished_threads(self) -> None:
        """Remove finished threads from the active threads list."""
        with self._threads_lock:
            self._active_threads = [t for t in self._active_threads if t.is_alive()]

    def wait_for_pending_sends(self, timeout: Optional[float] = None) -> None:
        """Wait for all pending send operations to complete.

        This method blocks until all background send threads have finished.
        Should be called before program exit to ensure all events are sent.

        Args:
            timeout: Maximum time to wait in seconds (None = wait indefinitely)
        """
        # Get a snapshot of active threads
        with self._threads_lock:
            threads_to_wait = self._active_threads.copy()

        # Wait for each thread to complete
        for thread in threads_to_wait:
            if thread.is_alive():
                thread.join(timeout=timeout)

        # Clean up finished threads
        self._cleanup_finished_threads()

    def close(self) -> None:
        """Close the HTTP session and cleanup resources."""
        self._session.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close the session."""
        self.close()













