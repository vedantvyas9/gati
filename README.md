# GATI SDK

**Local-First Observability Platform for AI Agents**

GATI is a comprehensive observability platform that helps you understand, debug, and optimize your AI agents. Track every LLM call, tool usage, and state change with minimal code changes.

---

## Features

- **Zero-Code Instrumentation** - Automatic tracking for LangChain and LangGraph
- **Local-First** - All trace data stays on your machine
- **Real-Time Cost Tracking** - Monitor LLM API costs and token usage
- **Visual Dashboard** - Beautiful React interface for exploring traces
- **AI Assistant Integration** - Query traces using Claude Desktop or GitHub Copilot via MCP
- **Privacy-Focused** - Trace data never leaves your machine; only anonymous usage metrics are collected

---

## Important: Usage Agreement & Authentication

> **⚠️ Before using GATI SDK, you must authenticate and agree to anonymous usage metrics collection.**

### What Data is Collected

When you use GATI SDK, the following anonymous metrics are automatically collected and sent to our telemetry backend:

**Metrics Collected:**

- Installation ID (anonymous UUID - no personal information)
- SDK version
- Framework detection (langchain/langgraph/custom)
- Number of agents tracked (count only)
- Number of events tracked (daily and lifetime counts)
- MCP query usage (count only)

**What is NOT Collected:**

- ❌ LLM prompts or completions
- ❌ Tool inputs or outputs
- ❌ API keys or credentials
- ❌ Your code or business logic
- ❌ IP addresses or device information
- ❌ Any personally identifiable information (except your verified email)

### Your Trace Data Stays Local

**All agent execution traces remain on your machine:**

- ✅ Stored in local SQLite database
- ✅ NOT sent to any external service
- ✅ Complete control and ownership
- ✅ View via local dashboard at `http://localhost:3000`

### Required: Authentication

To use the GATI SDK, you must first authenticate with your email:

```bash
# 1. Request verification code
gati auth
# Enter your email when prompted

# 2. Check your email and verify
gati auth verify <code-from-email>
```

**Why Authentication is Required:**

- Ensures responsible usage of the SDK
- Allows us to improve the product based on aggregated metrics
- Provides support channel if needed

**By authenticating, you agree that:**

- Anonymous usage metrics (as listed above) will be collected
- Your email will be stored for authentication purposes only
- All your trace data remains local on your machine

---

## Quick Start

### 1. Installation

```bash
pip install gati
```

### 2. Authentication (Required)

```bash
# Authenticate before first use
gati auth
# Follow the prompts to verify your email
```

### 3. Start the Backend

```bash
# Using Docker (recommended)
docker-compose up -d

# Or manually
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 4. Instrument Your Code

#### LangChain (Auto-instrumentation)

```python
from gati import observe

# Initialize once at the start of your application
observe.init(name="my_agent")

# Your existing LangChain code works automatically!
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate

llm = ChatOpenAI(model="gpt-4")
prompt = ChatPromptTemplate.from_template("Tell me a joke about {topic}")
chain = prompt | llm

# This will be automatically tracked
result = chain.invoke({"topic": "programming"})
```

#### LangGraph (Auto-instrumentation)

```python
from gati import observe
from langgraph.graph import StateGraph

observe.init(name="my_agent")

# Your LangGraph code is automatically instrumented
graph = StateGraph(AgentState)
graph.add_node("agent", call_model)
graph.add_node("action", call_tool)
# ... rest of your graph
app = graph.compile()  # Automatically wrapped!

result = app.invoke(initial_state)
```

#### Custom Code (Decorators)

```python
from gati import observe
from gati.decorators import track_agent, track_tool

observe.init(name="my_agent")

@track_agent(name="MyAgent")
def my_agent(query: str):
    result = research(query)
    return process(result)

@track_tool(name="web_search")
def research(query: str):
    # Your tool logic here
    return results
```

### 5. View the Dashboard

Open [http://localhost:3000](http://localhost:3000) to see your traces, costs, and execution timelines.

---

## Architecture

```
┌─────────────────────┐
│   Your Agent        │
│  (LangChain/        │
│   LangGraph)        │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐      ┌──────────────┐      ┌──────────────┐
│   GATI SDK          │─────▶│   Backend    │─────▶│  Dashboard   │
│   (Python)          │      │  (FastAPI)   │      │   (React)    │
└─────────────────────┘      └──────┬───────┘      └──────────────┘
                                     │
                                     ▼
                              ┌──────────────┐
                              │  MCP Server  │
                              │ (AI Assist)  │
                              └──────────────┘
```

---

## Components

- [**SDK**](sdk/README.md) - Python instrumentation library
- [**Backend**](backend/README.md) - FastAPI server with SQLite storage
- [**Dashboard**](dashboard/README.md) - React visualization interface
- [**MCP Server**](mcp-server/README.md) - Model Context Protocol integration
- [**Telemetry Backend**](telemetry-backend/README.md) - Optional anonymous usage analytics
- [**Demo**](demo/README.md) - Example implementations
- [**Tests**](tests/README.md) - Test suite

---

## Configuration

Create a `.env` file in the root directory:

```bash
# Copy the example configuration
cp .env.example .env
```

Key configuration options:

```env
# Backend
DATABASE_URL=sqlite+aiosqlite:///./gati.db
BACKEND_PORT=8000
TZ=America/Chicago  # Your timezone for display

# Dashboard
DASHBOARD_PORT=3000
VITE_BACKEND_URL=http://localhost:8000

# Telemetry (required - part of usage agreement)
GATI_TELEMETRY_URL=https://gati-mvp-telemetry.vercel.app/api/metrics
```

---

## CLI Commands

```bash
# Authentication (REQUIRED before using SDK)
gati auth                    # Request verification code via email
gati auth verify <code>      # Verify code and activate SDK
gati auth status             # Check authentication status

# Telemetry status
gati telemetry status        # Check telemetry status

# View help
gati --help
```

---

## MCP Integration

Connect GATI to Claude Desktop or GitHub Copilot to query traces using natural language:

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "gati": {
      "command": "node",
      "args": ["/path/to/gati-sdk/mcp-server/dist/index.js"],
      "env": {
        "DATABASE_PATH": "/path/to/gati-sdk/gati.db"
      }
    }
  }
}
```

### GitHub Copilot (VS Code)

Add to VS Code settings:

```json
{
  "github.copilot.mcpServers": {
    "gati": {
      "command": "node",
      "args": ["/path/to/gati-sdk/mcp-server/dist/index.js"],
      "env": {
        "DATABASE_PATH": "/path/to/gati-sdk/gati.db"
      }
    }
  }
}
```

Then ask questions like:

- "Show me all agents"
- "What was the cost of the last run?"
- "Compare the last 3 runs"
- "Why was run X slow?"

---

## Development

### Prerequisites

- Python 3.9+
- Node.js 18+
- Docker & Docker Compose (optional but recommended)

### Setup

```bash
# Clone the repository
git clone https://github.com/gati/gati-sdk.git
cd gati-sdk

# Install SDK in development mode
cd sdk
pip install -e .

# Start backend
cd ../backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Start dashboard (new terminal)
cd ../dashboard
npm install
npm run dev

# Build MCP server (new terminal)
cd ../mcp-server
npm install
npm run build
```

### Running Tests

```bash
cd tests
pytest
```

---

## Examples

See the [demo](demo/README.md) folder for complete examples:

- LangChain integration
- LangGraph state machines
- Custom decorators
- Multi-agent systems
- Tool usage tracking

---

## Troubleshooting

### Backend not connecting

```bash
# Check if backend is running
curl http://localhost:8000/health

# Check logs
docker-compose logs backend
```

### Dashboard not showing data

1. Verify backend URL in `.env`: `VITE_BACKEND_URL=http://localhost:8000`
2. Check browser console for errors
3. Ensure CORS is enabled (should be by default)

### Telemetry authentication issues

```bash
# Check authentication status
gati auth status

# Re-authenticate
gati auth
```

---

## License

MIT License - see [LICENSE](LICENSE) file for details

---

## Roadmap

- [ ] Support for more LLM frameworks (Haystack, AutoGen)
- [ ] Advanced cost optimization suggestions
- [ ] Custom metric definitions
- [ ] Team collaboration features
- [ ] Export to common formats (JSON, CSV, Parquet)

