/**
 * Database queries for GATI traces (SQLite)
 */
import { getDatabase } from './connection.js';

/**
 * Agent with statistics
 */
export interface AgentStats {
  name: string;
  description: string | null;
  total_runs: number;
  total_events: number;
  total_cost: number;
  avg_cost_per_run: number;
  created_at: string;
}

/**
 * Run details
 */
export interface RunDetails {
  run_id: string;
  run_name: string;
  agent_name: string;
  environment: string;
  status: string;
  total_duration_ms: number | null;
  total_cost: number | null;
  tokens_in: number | null;
  tokens_out: number | null;
  metadata: any;
  created_at: string;
  event_count: number;
}

/**
 * Event data
 */
export interface Event {
  event_id: string;
  run_id: string;
  agent_name: string;
  event_type: string;
  timestamp: string;
  parent_event_id: string | null;
  previous_event_id: string | null;
  data: any;
}

/**
 * List all agents with statistics
 */
export function listAgents(): AgentStats[] {
  const query = `
    SELECT
      a.name,
      a.description,
      COUNT(DISTINCT r.run_id) as total_runs,
      COUNT(e.event_id) as total_events,
      COALESCE(SUM(r.total_cost), 0) as total_cost,
      COALESCE(AVG(r.total_cost), 0) as avg_cost_per_run,
      a.created_at
    FROM agents a
    LEFT JOIN runs r ON a.name = r.agent_name
    LEFT JOIN events e ON r.run_id = e.run_id
    GROUP BY a.name, a.description, a.created_at
    ORDER BY a.created_at DESC
  `;

  return getDatabase().prepare(query).all() as AgentStats[];
}

/**
 * Get agent statistics
 */
export function getAgentStats(agentName: string): AgentStats | null {
  const query = `
    SELECT
      a.name,
      a.description,
      COUNT(DISTINCT r.run_id) as total_runs,
      COUNT(e.event_id) as total_events,
      COALESCE(SUM(r.total_cost), 0) as total_cost,
      COALESCE(AVG(r.total_cost), 0) as avg_cost_per_run,
      a.created_at
    FROM agents a
    LEFT JOIN runs r ON a.name = r.agent_name
    LEFT JOIN events e ON r.run_id = e.run_id
    WHERE a.name = ?
    GROUP BY a.name, a.description, a.created_at
  `;

  return getDatabase().prepare(query).get(agentName) as AgentStats | undefined || null;
}

/**
 * List runs for an agent
 */
export function listRuns(
  agentName: string,
  limit: number = 20,
  offset: number = 0
): RunDetails[] {
  const query = `
    SELECT
      r.run_id,
      r.run_name,
      r.agent_name,
      r.environment,
      r.status,
      r.total_duration_ms,
      r.total_cost,
      r.tokens_in,
      r.tokens_out,
      r.metadata,
      r.created_at,
      COUNT(e.event_id) as event_count
    FROM runs r
    LEFT JOIN events e ON r.run_id = e.run_id
    WHERE r.agent_name = ?
    GROUP BY r.run_id
    ORDER BY r.created_at DESC
    LIMIT ? OFFSET ?
  `;

  const rows = getDatabase().prepare(query).all(agentName, limit, offset) as RunDetails[];

  // Parse metadata JSON
  return rows.map(row => ({
    ...row,
    metadata: row.metadata ? JSON.parse(row.metadata as any) : null,
  }));
}

/**
 * Get run details by name
 */
export function getRunByName(
  agentName: string,
  runName: string
): RunDetails | null {
  const query = `
    SELECT
      r.run_id,
      r.run_name,
      r.agent_name,
      r.environment,
      r.status,
      r.total_duration_ms,
      r.total_cost,
      r.tokens_in,
      r.tokens_out,
      r.metadata,
      r.created_at,
      COUNT(e.event_id) as event_count
    FROM runs r
    LEFT JOIN events e ON r.run_id = e.run_id
    WHERE r.agent_name = ? AND r.run_name = ?
    GROUP BY r.run_id
  `;

  const row = getDatabase().prepare(query).get(agentName, runName) as RunDetails | undefined;

  if (!row) return null;

  // Parse metadata JSON
  return {
    ...row,
    metadata: row.metadata ? JSON.parse(row.metadata as any) : null,
  };
}

/**
 * Get timeline events for a run
 */
export function getRunTimeline(runId: string): Event[] {
  const query = `
    SELECT
      event_id,
      run_id,
      agent_name,
      event_type,
      timestamp,
      parent_event_id,
      previous_event_id,
      data
    FROM events
    WHERE run_id = ?
    ORDER BY timestamp ASC
  `;

  const rows = getDatabase().prepare(query).all(runId) as Event[];

  // Parse JSON data
  return rows.map(row => ({
    ...row,
    data: row.data ? JSON.parse(row.data as any) : null,
  }));
}

/**
 * Get execution trace (hierarchical tree)
 */
export function getExecutionTrace(runId: string): Event[] {
  const query = `
    SELECT
      event_id,
      run_id,
      agent_name,
      event_type,
      timestamp,
      parent_event_id,
      previous_event_id,
      data
    FROM events
    WHERE run_id = ?
    ORDER BY timestamp ASC
  `;

  const rows = getDatabase().prepare(query).all(runId) as Event[];

  // Parse JSON data
  return rows.map(row => ({
    ...row,
    data: row.data ? JSON.parse(row.data as any) : null,
  }));
}

/**
 * Search events by criteria
 */
export function searchEvents(
  agentName?: string,
  eventType?: string,
  startTime?: Date,
  endTime?: Date,
  limit: number = 100
): Event[] {
  const conditions: string[] = [];
  const params: any[] = [];

  if (agentName) {
    conditions.push('agent_name = ?');
    params.push(agentName);
  }

  if (eventType) {
    conditions.push('event_type = ?');
    params.push(eventType);
  }

  if (startTime) {
    conditions.push('timestamp >= ?');
    params.push(startTime.toISOString());
  }

  if (endTime) {
    conditions.push('timestamp <= ?');
    params.push(endTime.toISOString());
  }

  const whereClause = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';

  const query = `
    SELECT
      event_id,
      run_id,
      agent_name,
      event_type,
      timestamp,
      parent_event_id,
      previous_event_id,
      data
    FROM events
    ${whereClause}
    ORDER BY timestamp DESC
    LIMIT ?
  `;

  params.push(limit);

  const rows = getDatabase().prepare(query).all(...params) as Event[];

  // Parse JSON data
  return rows.map(row => ({
    ...row,
    data: row.data ? JSON.parse(row.data as any) : null,
  }));
}

/**
 * Get global metrics across all agents
 */
export function getGlobalMetrics(): any {
  const query = `
    SELECT
      COUNT(DISTINCT a.name) as total_agents,
      COUNT(DISTINCT r.run_id) as total_runs,
      COUNT(e.event_id) as total_events,
      COALESCE(SUM(r.total_cost), 0) as total_cost,
      COALESCE(AVG(r.total_cost), 0) as avg_cost_per_run,
      COALESCE(SUM(r.tokens_in), 0) as total_tokens_in,
      COALESCE(SUM(r.tokens_out), 0) as total_tokens_out,
      COALESCE(SUM(r.total_duration_ms), 0) / 3600000.0 as total_duration_hours
    FROM agents a
    LEFT JOIN runs r ON a.name = r.agent_name
    LEFT JOIN events e ON r.run_id = e.run_id
  `;

  return getDatabase().prepare(query).get();
}

/**
 * Get cost breakdown by model
 */
export function getCostBreakdown(agentName?: string): any[] {
  const agentFilter = agentName ? 'AND e.agent_name = ?' : '';
  const params = agentName ? [agentName] : [];

  const query = `
    SELECT
      json_extract(e.data, '$.model') as model,
      COUNT(*) as call_count,
      SUM(CAST(json_extract(e.data, '$.cost') AS REAL)) as total_cost,
      SUM(CAST(json_extract(e.data, '$.tokens_in') AS REAL)) as total_tokens_in,
      SUM(CAST(json_extract(e.data, '$.tokens_out') AS REAL)) as total_tokens_out,
      AVG(CAST(json_extract(e.data, '$.latency_ms') AS REAL)) as avg_latency_ms
    FROM events e
    WHERE e.event_type = 'llm_call'
      AND json_extract(e.data, '$.model') IS NOT NULL
      ${agentFilter}
    GROUP BY json_extract(e.data, '$.model')
    ORDER BY total_cost DESC
  `;

  return getDatabase().prepare(query).all(...params) as any[];
}

/**
 * Compare runs
 */
export function compareRuns(runIds: string[]): RunDetails[] {
  // SQLite doesn't have ANY operator, use IN instead
  const placeholders = runIds.map(() => '?').join(', ');

  const query = `
    SELECT
      r.run_id,
      r.run_name,
      r.agent_name,
      r.environment,
      r.status,
      r.total_duration_ms,
      r.total_cost,
      r.tokens_in,
      r.tokens_out,
      r.metadata,
      r.created_at,
      COUNT(e.event_id) as event_count
    FROM runs r
    LEFT JOIN events e ON r.run_id = e.run_id
    WHERE r.run_id IN (${placeholders})
    GROUP BY r.run_id
    ORDER BY r.created_at DESC
  `;

  const rows = getDatabase().prepare(query).all(...runIds) as RunDetails[];

  // Parse metadata JSON
  return rows.map(row => ({
    ...row,
    metadata: row.metadata ? JSON.parse(row.metadata as any) : null,
  }));
}
