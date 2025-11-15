# GATI Backend

FastAPI-based REST API server for receiving, storing, and serving AI agent trace data.

---

## Overview

The backend component is responsible for:

- Receiving trace events from the GATI SDK via HTTP
- Storing events in a local SQLite database (migrated from PostgreSQL)
- Providing REST API endpoints for the dashboard and MCP server
- Managing agent runs and event hierarchies
- Calculating costs and token usage metrics

---

## Architecture

```
┌─────────────────┐
│   GATI SDK      │
│  (Instrumented  │
│   Agent Code)   │
└────────┬────────┘
         │ HTTP POST
         ▼
┌─────────────────────────────────────┐
│         FastAPI Backend             │
│                                     │
│  ┌──────────────────────────────┐  │
│  │      API Endpoints           │  │
│  │  POST /api/events            │  │
│  │  GET  /api/agents            │  │
│  │  GET  /api/runs              │  │
│  │  GET  /api/metrics           │  │
│  └──────────────────────────────┘  │
│              │                      │
│              ▼                      │
│  ┌──────────────────────────────┐  │
│  │     SQLAlchemy ORM           │  │
│  └──────────────────────────────┘  │
│              │                      │
│              ▼                      │
│  ┌──────────────────────────────┐  │
│  │   SQLite Database (WAL)      │  │
│  │  • agents                    │  │
│  │  • runs                      │  │
│  │  • events                    │  │
│  └──────────────────────────────┘  │
└─────────────────────────────────────┘
         │
         ├──────────────┬──────────────┐
         ▼              ▼              ▼
  ┌──────────┐   ┌──────────┐   ┌──────────┐
  │Dashboard │   │MCP Server│   │  CLI     │
  └──────────┘   └──────────┘   └──────────┘
```

---

## Database Schema

### Tables

**agents**
- `id` (INTEGER, PK) - Auto-incrementing ID
- `name` (TEXT, UNIQUE) - Agent name
- `description` (TEXT, nullable) - Agent description
- `framework` (TEXT) - Framework type (langchain, langgraph, custom)
- `created_at` (TIMESTAMP) - First seen timestamp
- `updated_at` (TIMESTAMP) - Last activity timestamp

**runs**
- `id` (INTEGER, PK) - Auto-incrementing ID
- `run_id` (TEXT, UNIQUE) - UUID for the run
- `agent_id` (INTEGER, FK) - References agents.id
- `status` (TEXT) - success, error, running
- `started_at` (TIMESTAMP) - Run start time
- `ended_at` (TIMESTAMP, nullable) - Run end time
- `duration_ms` (INTEGER, nullable) - Total duration in milliseconds
- `total_cost` (REAL) - Total LLM API cost in USD
- `total_tokens` (INTEGER) - Total tokens used
- `error_message` (TEXT, nullable) - Error details if failed

**events**
- `id` (INTEGER, PK) - Auto-incrementing ID
- `event_id` (TEXT, UNIQUE) - UUID for the event
- `run_id` (TEXT, FK) - References runs.run_id
- `parent_event_id` (TEXT, nullable) - Parent event for hierarchy
- `event_type` (TEXT) - Type (agent_start, llm_call, tool_call, etc.)
- `timestamp` (TIMESTAMP) - Event timestamp
- `data` (JSON) - Event payload
- `duration_ms` (INTEGER, nullable) - Event duration
- `cost` (REAL, nullable) - Cost for this event
- `tokens` (INTEGER, nullable) - Tokens for this event

### Indexes

```sql
CREATE INDEX idx_runs_agent_id ON runs(agent_id);
CREATE INDEX idx_runs_started_at ON runs(started_at);
CREATE INDEX idx_events_run_id ON events(run_id);
CREATE INDEX idx_events_parent_id ON events(parent_event_id);
CREATE INDEX idx_events_timestamp ON events(timestamp);
```

---

## Installation

### Using Docker (Recommended)

```bash
cd backend
docker build -t gati-backend .
docker run -p 8000:8000 -v $(pwd)/gati.db:/app/gati.db gati-backend
```

### Manual Installation

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --port 8000
```

---

## Configuration

### Environment Variables

Create a `.env` file:

```bash
# Database
DATABASE_URL=sqlite+aiosqlite:///./gati.db

# Server
BACKEND_PORT=8000
HOST=0.0.0.0

# Timezone (for timestamp display)
TZ=America/Chicago

# CORS (comma-separated origins)
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# Admin (optional)
ADMIN_TOKEN=your-secret-token-here

# Logging
LOG_LEVEL=INFO
```

---

## API Endpoints

### Health Check

**GET /health**
```json
{
  "status": "healthy",
  "database": "connected",
  "version": "0.1.0"
}
```

### Event Ingestion

**POST /api/events**

Bulk event ingestion (up to 10,000 events per request).

Request:
```json
{
  "events": [
    {
      "event_id": "uuid",
      "run_id": "uuid",
      "parent_event_id": "uuid or null",
      "event_type": "agent_start",
      "timestamp": "2024-01-15T10:30:00Z",
      "data": {
        "agent_name": "ResearchAgent",
        "input": {"query": "What is AI?"}
      }
    }
  ]
}
```

Response:
```json
{
  "status": "success",
  "events_received": 1
}
```

### Agent Endpoints

**GET /api/agents**

List all tracked agents with statistics.

**GET /api/agents/{name}/runs**

Get all runs for a specific agent.

Query params:
- `limit` (int, default=50)
- `offset` (int, default=0)
- `status` (string, optional)

### Run Endpoints

**GET /api/runs/{run_id}**

Get detailed information about a specific run.

**GET /api/runs/{run_id}/timeline**

Get chronological event timeline.

**GET /api/runs/{run_id}/trace**

Get hierarchical execution trace.

### Metrics Endpoints

**GET /api/metrics/summary**

Get global metrics across all agents and runs.

---

## Database Migrations

### Creating a Migration

```bash
# After modifying models in app/models/
alembic revision --autogenerate -m "Description of changes"
```

### Applying Migrations

```bash
# Upgrade to latest
alembic upgrade head

# Upgrade one version
alembic upgrade +1

# Downgrade one version
alembic downgrade -1

# Show current version
alembic current
```

---

## Development

### Project Structure

```
backend/
├── alembic/              # Database migrations
│   ├── versions/         # Migration files
│   └── env.py           # Alembic config
├── app/
│   ├── main.py          # FastAPI application
│   ├── api/             # API route handlers
│   │   ├── events.py    # Event ingestion
│   │   ├── agents.py    # Agent endpoints
│   │   ├── runs.py      # Run endpoints
│   │   └── metrics.py   # Metrics endpoints
│   ├── database/        # Database connection
│   ├── models/          # SQLAlchemy models
│   ├── schemas/         # Pydantic schemas
│   ├── services/        # Business logic
│   └── utils/           # Utilities
├── Dockerfile           # Container build
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run all tests
pytest

# Run with coverage
pytest --cov=app
```

### Local Development

```bash
# Start with auto-reload
uvicorn app.main:app --reload --port 8000

# Enable debug logging
LOG_LEVEL=DEBUG uvicorn app.main:app --reload
```

---

## Performance

### Optimization Features

- **Bulk Inserts**: Events inserted in batches (up to 10,000)
- **Connection Pooling**: Async connection pool
- **WAL Mode**: SQLite Write-Ahead Logging for concurrent reads
- **Indexed Queries**: Strategic indexes on foreign keys and timestamps
- **Async I/O**: All database operations are async

### Benchmarks

- **Event Ingestion**: ~5,000 events/second
- **Query Response**: <50ms for most queries
- **Database Size**: ~1KB per event

---

## Troubleshooting

### Database Locked Errors

```bash
# Check if WAL mode is enabled
sqlite3 gati.db "PRAGMA journal_mode;"

# Enable WAL mode manually
sqlite3 gati.db "PRAGMA journal_mode=WAL;"
```

### Migration Issues

```bash
# Reset database (CAUTION: deletes all data)
rm gati.db
alembic upgrade head
```

### CORS Errors

Add your frontend URL to CORS_ORIGINS:

```bash
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

---

## Security

### Best Practices

- Never expose backend directly to internet
- Set ADMIN_TOKEN for protected endpoints
- Use HTTPS in production
- Implement rate limiting in reverse proxy
- Regular database backups

---

## Backup & Restore

### Backup

```bash
# Stop backend first
docker-compose stop backend

# Backup database
cp backend/gati.db backend/gati.db.backup-$(date +%Y%m%d)
```

### Restore

```bash
# Stop backend
docker-compose stop backend

# Restore from backup
cp backend/gati.db.backup-20240115 backend/gati.db

# Start backend
docker-compose start backend
```

---

## License

MIT License - see [LICENSE](../LICENSE) for details
