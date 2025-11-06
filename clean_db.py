"""Clean GATI database."""
import psycopg2

try:
    conn = psycopg2.connect(
        host="localhost",
        port=5434,
        database="gati_db",
        user="gati_user",
        password="gati_password"
    )

    cursor = conn.cursor()

    # Delete all events
    cursor.execute("DELETE FROM events")
    events_deleted = cursor.rowcount

    # Delete all runs
    cursor.execute("DELETE FROM runs")
    runs_deleted = cursor.rowcount

    # Delete all agents
    cursor.execute("DELETE FROM agents")
    agents_deleted = cursor.rowcount

    conn.commit()

    print(f"✓ Cleaned database:")
    print(f"  - Deleted {events_deleted} events")
    print(f"  - Deleted {runs_deleted} runs")
    print(f"  - Deleted {agents_deleted} agents")

    cursor.close()
    conn.close()

except Exception as e:
    print(f"✗ Error: {e}")
