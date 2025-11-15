# GATI Dashboard

Modern React-based web interface for visualizing and exploring AI agent traces.

---

## Overview

The dashboard provides a visual interface for:

- Browsing all tracked agents and their statistics
- Viewing agent execution runs with detailed timelines
- Exploring hierarchical event traces
- Analyzing costs, token usage, and performance metrics
- Debugging agent behavior and errors

---

## Features

- **Agent List View** - Overview of all agents with aggregated statistics
- **Run Browser** - Browse all runs for a specific agent with filtering
- **Timeline View** - Chronological visualization of events
- **Execution Graph** - Hierarchical tree visualization using ReactFlow
- **Cost Analytics** - Detailed breakdown of LLM costs and token usage
- **Real-time Updates** - Auto-refresh for active runs
- **Dark Mode** - Modern dark theme optimized for readability
- **Responsive Design** - Works on desktop and tablet devices

---

## Tech Stack

- **React 18** - UI framework
- **TypeScript** - Type-safe development
- **Vite** - Fast build tool and dev server
- **React Router** - Client-side routing
- **Tailwind CSS** - Utility-first styling
- **Recharts** - Data visualization charts
- **ReactFlow** - Interactive execution graphs
- **Axios** - HTTP client for backend API

---

## Installation

### Using Docker (Recommended)

```bash
cd dashboard
docker build -t gati-dashboard .
docker run -p 3000:80 gati-dashboard
```

### Manual Installation

```bash
cd dashboard

# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

---

## Configuration

### Environment Variables

Create a `.env` file:

```bash
# Backend API URL
VITE_BACKEND_URL=http://localhost:8000

# Port for development server
PORT=3000
```

---

## Project Structure

```
dashboard/
├── public/               # Static assets
├── src/
│   ├── components/      # Reusable UI components
│   │   ├── AgentCard.tsx
│   │   ├── RunCard.tsx
│   │   ├── Timeline.tsx
│   │   ├── ExecutionGraph.tsx
│   │   └── CostChart.tsx
│   ├── pages/          # Route pages
│   │   ├── AgentsPage.tsx
│   │   ├── AgentDetailPage.tsx
│   │   ├── RunDetailPage.tsx
│   │   └── NotFoundPage.tsx
│   ├── services/       # API client
│   │   └── api.ts      # Axios backend client
│   ├── hooks/          # Custom React hooks
│   │   ├── useAgents.ts
│   │   ├── useRuns.ts
│   │   └── usePolling.ts
│   ├── types/          # TypeScript definitions
│   │   └── index.ts    # Shared types
│   ├── styles/         # Global styles
│   │   └── index.css
│   ├── App.tsx         # Main app component
│   └── main.tsx        # Entry point
├── index.html          # HTML template
├── vite.config.ts      # Vite configuration
├── tailwind.config.js  # Tailwind CSS config
├── tsconfig.json       # TypeScript config
└── package.json        # Dependencies
```

---

## API Integration

The dashboard communicates with the GATI backend via REST API.

### Endpoints Used

- `GET /api/agents` - List all agents
- `GET /api/agents/{name}/runs` - Get runs for agent
- `GET /api/runs/{run_id}` - Get run details
- `GET /api/runs/{run_id}/timeline` - Get event timeline
- `GET /api/runs/{run_id}/trace` - Get execution tree
- `GET /api/metrics/summary` - Global metrics

---

## Development

### Running Development Server

```bash
npm run dev
```

Dashboard available at [http://localhost:3000](http://localhost:3000).

### Building for Production

```bash
npm run build
# Output: dist/
```

### Type Checking

```bash
npx tsc --noEmit
```

---

## Deployment

### Production Build

```bash
npm run build
```

### Nginx Configuration

See [nginx.conf](nginx.conf:1) for production server setup.

### Docker Deployment

```bash
docker build -t gati-dashboard .
docker run -p 3000:80 gati-dashboard
```

### Static Hosting

Deploy `dist/` folder to:
- **Vercel** - `vercel deploy`
- **Netlify** - Drag and drop
- **GitHub Pages** - Push to gh-pages branch
- **AWS S3** - Upload to bucket

---

## Troubleshooting

### Backend Connection Issues

```bash
# Check backend URL
cat .env

# Verify backend is running
curl http://localhost:8000/health
```

### Build Errors

```bash
# Clear and reinstall
rm -rf node_modules package-lock.json
npm install
```

---

## Browser Support

- Chrome/Edge: Latest 2 versions
- Firefox: Latest 2 versions
- Safari: Latest 2 versions
- Mobile: iOS 12+, Android 8+

---

## License

MIT License - see [LICENSE](../LICENSE) for details
