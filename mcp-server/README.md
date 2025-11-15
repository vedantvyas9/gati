# GATI MCP Server

Model Context Protocol (MCP) server for querying GATI traces directly from AI assistants like Claude Desktop and GitHub Copilot.

---

## Overview

The GATI MCP Server exposes your local trace data through a set of tools that AI assistants can use to help you analyze and understand your agent's behavior, costs, and performance.

---

## Features

### Available Tools

1. **list_agents** - List all tracked agents with statistics
2. **get_agent_stats** - Get detailed statistics for a specific agent
3. **list_runs** - List all runs for an agent
4. **get_run_details** - Get detailed information about a specific run
5. **get_run_timeline** - Get chronological timeline of events
6. **get_execution_trace** - Get hierarchical execution tree
7. **compare_runs** - Compare metrics across multiple runs
8. **search_events** - Search events by various criteria
9. **get_cost_breakdown** - Analyze costs by LLM model
10. **get_global_metrics** - Get global metrics across all agents

---

## Quick Start (Docker Compose)

### Prerequisites

- Docker and Docker Compose installed
- GATI SDK collecting traces to PostgreSQL

### Setup

1. Start the GATI stack (including MCP server):

```bash
cd gati-sdk
docker-compose up -d
```

2. Configure your AI assistant:

**For Claude Desktop:**
```bash
./scripts/configure-claude-desktop.sh
```

**For VS Code with GitHub Copilot:**
```bash
./scripts/configure-copilot.sh
```

3. Restart your AI assistant

4. Start querying your traces!

---

## Usage Examples

### With Claude Desktop

```
You: "Show me all my agents"
Claude: [Uses list_agents tool automatically]

You: "What was the cost for my chatbot agent's last 5 runs?"
Claude: [Uses list_runs and analyzes the data]

You: "Show me the execution trace for run 3"
Claude: [Uses get_execution_trace to show the hierarchical flow]

You: "Why was run 5 so expensive compared to run 4?"
Claude: [Uses compare_runs and get_run_details to analyze]
```

### With GitHub Copilot in VS Code

```
You: @gati show me all agents
Copilot: [Invokes list_agents tool and shows results]

You: @gati compare the last 3 runs for my-agent
Copilot: [Uses compare_runs tool]
```

---

## Architecture

```
Docker Compose Stack:
┌─────────────────────────┐
│  PostgreSQL             │ ← Stores trace data
│  (port 5434)            │
└───────────┬─────────────┘
            │
┌───────────▼─────────────┐
│  GATI MCP Server        │ ← Exposes traces via MCP
│  (stdio interface)      │
└───────────┬─────────────┘
            │
┌───────────▼─────────────┐
│  Claude Desktop /       │ ← AI assistant
│  GitHub Copilot         │
└─────────────────────────┘
```

---

## Configuration

The MCP server is configured via environment variables in docker-compose.yml:

```yaml
environment:
  DATABASE_URL: postgresql://gati_user:gati_password@postgres:5432/gati_db
  DATABASE_POOL_SIZE: 10
  DATABASE_POOL_TIMEOUT: 30000
```

---

## Development

### Local Development (without Docker)

1. Install dependencies:
```bash
cd mcp-server
npm install
```

2. Set database URL:
```bash
export DATABASE_URL="postgresql://gati_user:gati_password@localhost:5434/gati_db"
```

3. Run in development mode:
```bash
npm run dev
```

4. Build:
```bash
npm run build
```

---

## Troubleshooting

### MCP server not connecting

1. Check if containers are running:
```bash
docker-compose ps
```

2. Check MCP server logs:
```bash
docker-compose logs mcp-server
```

3. Test database connection:
```bash
docker-compose exec mcp-server node -e "console.log('Database URL:', process.env.DATABASE_URL)"
```

### Tools not appearing in AI assistant

1. Verify configuration file location:
   - Claude Desktop: `~/Library/Application Support/Claude/claude_desktop_config.json` (Mac)
   - VS Code: Settings → Extensions → GitHub Copilot → MCP Servers

2. Restart the AI assistant completely

3. Check MCP server is in the config:
```bash
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json | grep gati
```

### No trace data showing up

1. Verify PostgreSQL has data:
```bash
docker-compose exec postgres psql -U gati_user -d gati_db -c "SELECT COUNT(*) FROM agents;"
```

2. Check that your SDK is configured to send to the correct backend:
```python
from gati import Observe

observe = Observe.init(
    backend_url="http://localhost:8000",  # Make sure this matches your setup
    agent_name="my-agent"
)
```

---

## License

MIT
