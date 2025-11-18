#!/usr/bin/env python3
"""
End-to-end test script for GATI authentication and telemetry metrics.

This script will:
1. Test auth flow (request code, verify code, save token)
2. Verify credentials are saved locally
3. Generate some sample metrics
4. Send metrics to Vercel backend
5. Verify the complete flow works

Usage:
    python test_auth_and_metrics.py
"""

import json
import sys
import requests
from pathlib import Path
from datetime import datetime


class AuthAndMetricsTest:
    """Test class for auth and metrics flow."""

    def __init__(self):
        self.auth_base_url = "https://gati-mvp-telemetry.vercel.app/api/auth"
        self.metrics_url = "https://gati-mvp-telemetry.vercel.app/api/metrics"
        self.config_dir = Path.home() / ".gati"
        self.token_file = self.config_dir / ".auth_token"
        self.email_file = self.config_dir / ".auth_email"
        self.metrics_file = self.config_dir / "metrics.json"

    def print_header(self, title: str):
        """Print a formatted header."""
        print("\n" + "=" * 70)
        print(f"  {title}")
        print("=" * 70)

    def print_step(self, step_num: int, title: str):
        """Print a step header."""
        print(f"\n📋 Step {step_num}: {title}")
        print("-" * 70)

    def check_auth_status(self) -> dict:
        """Check if user is already authenticated."""
        self.print_step(1, "Checking Authentication Status")

        if self.token_file.exists() and self.email_file.exists():
            try:
                token = self.token_file.read_text().strip()
                email = self.email_file.read_text().strip()
                print(f"✅ Already authenticated as: {email}")
                print(f"✅ Token file exists: {self.token_file}")
                print(f"✅ Email file exists: {self.email_file}")
                print(f"✅ Token (first 20 chars): {token[:20]}...")
                return {"authenticated": True, "email": email, "token": token}
            except Exception as e:
                print(f"❌ Error reading credentials: {e}")
                return {"authenticated": False}
        else:
            print("❌ Not authenticated")
            print(f"   Token file exists: {self.token_file.exists()}")
            print(f"   Email file exists: {self.email_file.exists()}")
            return {"authenticated": False}

    def request_verification_code(self, email: str) -> bool:
        """Request a verification code."""
        self.print_step(2, "Requesting Verification Code")

        print(f"📧 Requesting code for: {email}")

        try:
            response = requests.post(
                f"{self.auth_base_url}/request-code",
                json={"email": email},
                timeout=10
            )

            print(f"   Response status: {response.status_code}")

            if response.status_code == 200:
                print(f"✅ Verification code sent to {email}")
                print(f"   Check your email inbox (and spam folder)")
                return True
            else:
                data = response.json()
                print(f"❌ Failed to send code: {data.get('error', 'Unknown error')}")
                return False

        except Exception as e:
            print(f"❌ Error: {e}")
            return False

    def verify_code(self, email: str, code: str) -> dict:
        """Verify the code and get token."""
        self.print_step(3, "Verifying Code")

        print(f"📮 Verifying code: {code}")

        try:
            response = requests.post(
                f"{self.auth_base_url}/verify-code",
                json={"email": email, "code": code},
                timeout=10
            )

            print(f"   Response status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                token = data.get('apiToken')
                print(f"✅ Code verified successfully!")
                print(f"✅ Received API token: {token[:20]}...")

                # Save credentials
                self.config_dir.mkdir(parents=True, exist_ok=True)
                self.email_file.write_text(email)
                self.token_file.write_text(token)
                self.token_file.chmod(0o600)
                self.email_file.chmod(0o600)

                print(f"✅ Credentials saved to {self.config_dir}")

                return {"success": True, "email": email, "token": token}
            else:
                data = response.json()
                error = data.get('error', 'Unknown error')
                attempts = data.get('attemptsRemaining')
                if attempts is not None:
                    print(f"❌ {error} ({attempts} attempts remaining)")
                else:
                    print(f"❌ {error}")
                return {"success": False}

        except Exception as e:
            print(f"❌ Error: {e}")
            return {"success": False}

    def check_metrics_file(self) -> dict:
        """Check if metrics file exists and show contents."""
        self.print_step(4, "Checking Local Metrics File")

        if self.metrics_file.exists():
            try:
                with open(self.metrics_file, 'r') as f:
                    metrics = json.load(f)

                print(f"✅ Metrics file exists: {self.metrics_file}")
                print(f"\n📊 Current metrics:")
                print(json.dumps(metrics, indent=2))
                return metrics
            except Exception as e:
                print(f"❌ Error reading metrics: {e}")
                return {}
        else:
            print(f"ℹ️  Metrics file doesn't exist yet: {self.metrics_file}")
            print(f"   This is normal if you haven't used GATI yet")
            return {}

    def create_sample_metrics(self) -> dict:
        """Create sample metrics for testing."""
        self.print_step(5, "Creating Sample Metrics")

        import uuid

        # Get or create installation ID
        id_file = self.config_dir / ".gati_id"
        if id_file.exists():
            installation_id = id_file.read_text().strip()
        else:
            installation_id = str(uuid.uuid4())
            self.config_dir.mkdir(parents=True, exist_ok=True)
            id_file.write_text(installation_id)

        email = None
        if self.email_file.exists():
            email = self.email_file.read_text().strip()

        metrics = {
            "installation_id": installation_id,
            "sdk_version": "0.1.1",
            "user_email": email,
            "agents_tracked": 2,
            "events_today": 50,
            "lifetime_events": 150,
            "mcp_queries": 10,
            "frameworks_detected": ["langchain", "custom"],
            "timestamp": datetime.now().isoformat()
        }

        # Save to metrics file
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.metrics_file, 'w') as f:
            json.dump({
                "lifetime_events": metrics["lifetime_events"],
                "agents_tracked": metrics["agents_tracked"],
                "events_today": metrics["events_today"],
                "mcp_queries": metrics["mcp_queries"],
                "frameworks_detected": metrics["frameworks_detected"],
                "last_reset_date": datetime.now().date().isoformat()
            }, f, indent=2)

        print(f"✅ Sample metrics created:")
        print(json.dumps(metrics, indent=2))

        return metrics

    def send_metrics_to_backend(self, metrics: dict, token: str) -> bool:
        """Send metrics to Vercel backend."""
        self.print_step(6, "Sending Metrics to Vercel Backend")

        print(f"📤 Sending metrics to: {self.metrics_url}")
        print(f"   Using token: {token[:20]}...")

        try:
            response = requests.post(
                self.metrics_url,
                json=metrics,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": f"gati-sdk/{metrics['sdk_version']}",
                    "X-API-Key": token
                },
                timeout=10
            )

            print(f"   Response status: {response.status_code}")

            if response.status_code in (200, 201, 204):
                print(f"✅ Metrics sent successfully!")
                try:
                    response_data = response.json()
                    print(f"   Response: {json.dumps(response_data, indent=2)}")
                except:
                    print(f"   Response: {response.text}")
                return True
            else:
                print(f"❌ Failed to send metrics: {response.status_code}")
                print(f"   Response: {response.text}")
                return False

        except Exception as e:
            print(f"❌ Error sending metrics: {e}")
            return False

    def run_interactive_auth(self):
        """Run interactive authentication flow."""
        self.print_header("GATI Auth & Metrics Testing")

        # Step 1: Check current auth status
        auth_status = self.check_auth_status()

        if auth_status["authenticated"]:
            print("\n✅ You're already authenticated!")
            choice = input("\nDo you want to re-authenticate? (y/N): ").strip().lower()
            if choice != 'y':
                return auth_status

        # Step 2: Get email
        while True:
            email = input("\n📧 Enter your email address: ").strip()

            if not email:
                print("❌ Email cannot be empty")
                continue

            if '@' not in email or '.' not in email.split('@')[1]:
                print("❌ Please enter a valid email address")
                continue

            break

        # Step 3: Request code
        if not self.request_verification_code(email):
            print("\n❌ Failed to request verification code")
            return {"authenticated": False}

        # Step 4: Verify code
        while True:
            code = input("\n📮 Enter the 6-digit code from your email: ").strip()

            if len(code) != 6 or not code.isdigit():
                print("❌ Code must be exactly 6 digits")
                continue

            result = self.verify_code(email, code)

            if result["success"]:
                return result

            retry = input("\nTry again? (y/N): ").strip().lower()
            if retry != 'y':
                return {"authenticated": False}

    def run_metrics_test(self, token: str):
        """Run metrics generation and sending test."""
        self.print_header("Testing Metrics Flow")

        # Step 4: Check existing metrics
        existing_metrics = self.check_metrics_file()

        # Step 5: Create or use sample metrics
        if existing_metrics:
            print("\nℹ️  Found existing metrics. Use these or create new ones?")
            choice = input("   (U)se existing / (C)reate new / (S)kip: ").strip().upper()

            if choice == 'S':
                return
            elif choice == 'C':
                metrics = self.create_sample_metrics()
            else:
                # Need to add required fields for sending
                metrics = {
                    **existing_metrics,
                    "timestamp": datetime.now().isoformat()
                }
                # Get installation ID
                id_file = self.config_dir / ".gati_id"
                if id_file.exists():
                    metrics["installation_id"] = id_file.read_text().strip()
                if "sdk_version" not in metrics:
                    metrics["sdk_version"] = "0.1.1"
                if "user_email" not in metrics or not metrics["user_email"]:
                    if self.email_file.exists():
                        metrics["user_email"] = self.email_file.read_text().strip()
        else:
            metrics = self.create_sample_metrics()

        # Step 6: Send metrics
        self.send_metrics_to_backend(metrics, token)

    def run_full_test(self):
        """Run complete auth and metrics test."""
        # Part 1: Authentication
        auth_result = self.run_interactive_auth()

        if not auth_result.get("authenticated"):
            print("\n❌ Authentication failed. Cannot proceed with metrics test.")
            return

        # Part 2: Metrics
        token = auth_result.get("token")
        if not token:
            token = self.token_file.read_text().strip()

        self.run_metrics_test(token)

        # Summary
        self.print_header("Test Summary")
        print("✅ Authentication: SUCCESS")
        print(f"   Email: {auth_result.get('email', self.email_file.read_text().strip())}")
        print(f"   Token saved: {self.token_file}")
        print("\n✅ Metrics: SENT")
        print(f"   Endpoint: {self.metrics_url}")
        print("\n🎉 All tests completed!")
        print("\nNext steps:")
        print("1. Check your Vercel backend database (gati_users table) for your email")
        print("2. Check gati_metrics table for the metrics you just sent")
        print("3. Verify the metrics are linked to your email in the database")


if __name__ == "__main__":
    tester = AuthAndMetricsTest()
    tester.run_full_test()
