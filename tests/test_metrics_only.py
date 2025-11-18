#!/usr/bin/env python3
"""
Quick script to manually send metrics to Vercel backend.
Assumes you're already authenticated (gati auth completed).

Usage:
    python test_metrics_only.py
"""

import json
import requests
from pathlib import Path
from datetime import datetime
import uuid


def main():
    print("\n" + "=" * 70)
    print("  GATI Metrics Sender - Quick Test")
    print("=" * 70)

    # Configuration
    config_dir = Path.home() / ".gati"
    token_file = config_dir / ".auth_token"
    email_file = config_dir / ".auth_email"
    id_file = config_dir / ".gati_id"
    metrics_url = "https://gati-mvp-telemetry.vercel.app/api/metrics"

    # Check authentication
    print("\n📋 Step 1: Checking authentication...")
    if not token_file.exists() or not email_file.exists():
        print("❌ Not authenticated!")
        print(f"   Please run 'gati auth' first or use test_auth_and_metrics.py")
        return

    token = token_file.read_text().strip()
    email = email_file.read_text().strip()
    print(f"✅ Authenticated as: {email}")
    print(f"✅ Token (first 20 chars): {token[:20]}...")

    # Get or create installation ID
    print("\n📋 Step 2: Getting installation ID...")
    if id_file.exists():
        installation_id = id_file.read_text().strip()
        print(f"✅ Found existing installation ID: {installation_id}")
    else:
        installation_id = str(uuid.uuid4())
        config_dir.mkdir(parents=True, exist_ok=True)
        id_file.write_text(installation_id)
        print(f"✅ Created new installation ID: {installation_id}")

    # Create sample metrics
    print("\n📋 Step 3: Creating sample metrics...")
    metrics = {
        "installation_id": installation_id,
        "sdk_version": "0.1.1",
        "user_email": email,
        "agents_tracked": 3,
        "events_today": 75,
        "lifetime_events": 225,
        "mcp_queries": 15,
        "frameworks_detected": ["langchain", "langgraph", "custom"],
        "timestamp": datetime.now().isoformat()
    }

    print("✅ Metrics to send:")
    print(json.dumps(metrics, indent=2))

    # Send to backend
    print(f"\n📋 Step 4: Sending to Vercel backend...")
    print(f"   URL: {metrics_url}")

    try:
        response = requests.post(
            metrics_url,
            json=metrics,
            headers={
                "Content-Type": "application/json",
                "User-Agent": f"gati-sdk/{metrics['sdk_version']}",
                "X-API-Key": token
            },
            timeout=10
        )

        print(f"\n📊 Response:")
        print(f"   Status code: {response.status_code}")

        if response.status_code in (200, 201, 204):
            print("✅ SUCCESS! Metrics sent to Vercel backend")

            try:
                response_data = response.json()
                print(f"\n   Backend response:")
                print(json.dumps(response_data, indent=2))
            except:
                print(f"   Response text: {response.text}")

            print("\n" + "=" * 70)
            print("  ✅ METRICS SUCCESSFULLY SENT!")
            print("=" * 70)
            print("\n📝 Next steps:")
            print("   1. Check your Vercel backend database")
            print("   2. Look in 'gati_metrics' table")
            print(f"   3. Filter by user_email: {email}")
            print(f"   4. Filter by installation_id: {installation_id}")
            print("\n   You should see the metrics with timestamp:", metrics["timestamp"])

        else:
            print(f"❌ FAILED! Status code: {response.status_code}")
            print(f"   Response: {response.text}")

    except requests.exceptions.Timeout:
        print("❌ Request timed out")
    except requests.exceptions.ConnectionError:
        print("❌ Connection error - check internet connection")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
