// API Response Types

export interface Agent {
  name: string
  description?: string
  created_at: string
  updated_at?: string
  total_runs?: number
  total_events?: number
  total_cost?: number
  avg_cost?: number
}

export interface Run {
  run_name: string
  agent_name: string
  environment?: string
  status: 'active' | 'completed' | 'failed'
  total_duration_ms: number
  total_cost: number
  tokens_in: number
  tokens_out: number
  event_count?: number
  created_at: string
  updated_at?: string
  run_metadata?: Record<string, unknown>
}

export type RunResponse = Run

export interface Event {
  event_id: string
  run_name: string
  agent_name: string
  event_type: string
  timestamp: string
  data: Record<string, unknown>
  created_at: string
  updated_at?: string
  latency_ms?: number
}

export interface Metrics {
  total_agents: number
  total_runs: number
  total_events: number
  total_cost: number
  avg_cost_per_run: number
  total_tokens_in: number
  total_tokens_out: number
  total_duration_hours: number
  top_agents_by_cost: Array<{ agent_name: string; cost: number }>
  top_agents_by_runs: Array<{ agent_name: string; runs: number }>
}

export interface AgentWithStats extends Agent {
  total_runs: number
  total_events: number
  total_cost: number
  avg_cost: number
}

export interface RunTimeline {
  run_name: string
  agent_name: string
  events: Event[]
}

export interface ExecutionTreeNode extends Event {
  children?: ExecutionTreeNode[]
  depth?: number
}

export interface ExecutionTrace {
  run_name: string
  agent_name: string
  execution_tree: ExecutionTreeNode[]
  total_cost: number
  total_duration_ms: number
}

export interface ExecutionTreeNodeResponse extends Event {
  parent_event_id?: string
  latency_ms?: number
  cost?: number
  tokens_in?: number
  tokens_out?: number
  children?: ExecutionTreeNodeResponse[]
}

export interface ExecutionTraceResponseData {
  run_name: string
  agent_name: string
  total_cost: number
  total_duration_ms: number
  total_tokens_in: number
  total_tokens_out: number
  execution_tree: ExecutionTreeNodeResponse[]
}

export interface CostTimestampData {
  timestamp: string
  cost: number
  cumulative_cost: number
}

export interface TokensTimestampData {
  timestamp: string
  tokens_in: number
  tokens_out: number
  cumulative_tokens_in: number
  cumulative_tokens_out: number
}

export interface AgentComparisonData {
  agent_name: string
  runs: number
  cost: number
  avg_cost_per_run: number
  total_tokens: number
}

export interface MetricsSummary {
  total_agents: number
  total_runs: number
  total_events: number
  total_cost: number
  avg_cost_per_run: number
  avg_tokens_in_per_run: number
  avg_tokens_out_per_run: number
  total_tokens_in: number
  total_tokens_out: number
  total_duration_hours: number
  top_agents_by_cost: Array<{ agent_name: string; cost: number }>
  top_agents_by_runs: Array<{ agent_name: string; runs: number }>
}
