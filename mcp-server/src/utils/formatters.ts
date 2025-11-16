/**
 * Formatting utilities for LLM-friendly output
 */
import { AgentStats, RunDetails, Event } from '../database/queries.js';

/**
 * Format agents list for LLM consumption
 */
export function formatAgentsList(agents: AgentStats[]): string {
  if (agents.length === 0) {
    return 'No agents found. Start tracking your agents by using the GATI SDK.';
  }

  let output = `Found ${agents.length} agent(s):\n\n`;

  agents.forEach((agent, index) => {
    output += `${index + 1}. **${agent.name}**\n`;
    if (agent.description) {
      output += `   Description: ${agent.description}\n`;
    }
    output += `   Total Runs: ${agent.total_runs}\n`;
    output += `   Total Events: ${agent.total_events}\n`;
    output += `   Total Cost: $${Number(agent.total_cost).toFixed(4)}\n`;
    output += `   Avg Cost/Run: $${Number(agent.avg_cost_per_run).toFixed(4)}\n`;
    output += `   Created: ${agent.created_at}\n\n`;
  });

  return output;
}

/**
 * Format agent stats for LLM consumption
 */
export function formatAgentStats(agent: AgentStats): string {
  let output = `# Agent: ${agent.name}\n\n`;

  if (agent.description) {
    output += `**Description:** ${agent.description}\n\n`;
  }

  output += `## Statistics\n\n`;
  output += `- **Total Runs:** ${agent.total_runs}\n`;
  output += `- **Total Events:** ${agent.total_events}\n`;
  output += `- **Total Cost:** $${Number(agent.total_cost).toFixed(4)}\n`;
  output += `- **Average Cost per Run:** $${Number(agent.avg_cost_per_run).toFixed(4)}\n`;
  output += `- **Created:** ${agent.created_at}\n`;

  return output;
}

/**
 * Format runs list for LLM consumption
 */
export function formatRunsList(runs: RunDetails[]): string {
  if (runs.length === 0) {
    return 'No runs found for this agent.';
  }

  let output = `Found ${runs.length} run(s):\n\n`;

  runs.forEach((run, index) => {
    output += `${index + 1}. **${run.run_name}** (${run.status})\n`;
    output += `   Environment: ${run.environment}\n`;
    output += `   Duration: ${run.total_duration_ms ? `${run.total_duration_ms.toFixed(0)}ms` : 'N/A'}\n`;
    output += `   Cost: ${run.total_cost ? `$${Number(run.total_cost).toFixed(4)}` : 'N/A'}\n`;
    output += `   Tokens: ${run.tokens_in || 0} in, ${run.tokens_out || 0} out\n`;
    output += `   Events: ${run.event_count}\n`;
    output += `   Created: ${run.created_at}\n\n`;
  });

  return output;
}

/**
 * Format run details for LLM consumption
 */
export function formatRunDetails(run: RunDetails): string {
  let output = `# Run: ${run.run_name}\n\n`;
  output += `**Agent:** ${run.agent_name}\n`;
  output += `**Status:** ${run.status}\n`;
  output += `**Environment:** ${run.environment}\n\n`;

  output += `## Metrics\n\n`;
  output += `- **Duration:** ${run.total_duration_ms ? `${run.total_duration_ms.toFixed(0)}ms` : 'N/A'}\n`;
  output += `- **Cost:** ${run.total_cost ? `$${Number(run.total_cost).toFixed(4)}` : 'N/A'}\n`;
  output += `- **Input Tokens:** ${run.tokens_in || 0}\n`;
  output += `- **Output Tokens:** ${run.tokens_out || 0}\n`;
  output += `- **Total Events:** ${run.event_count}\n`;
  output += `- **Created:** ${run.created_at}\n\n`;

  if (run.metadata && Object.keys(run.metadata).length > 0) {
    output += `## Metadata\n\n`;
    output += `\`\`\`json\n${JSON.stringify(run.metadata, null, 2)}\n\`\`\`\n\n`;
  }

  return output;
}

/**
 * Format timeline events for LLM consumption
 */
export function formatTimeline(events: Event[]): string {
  if (events.length === 0) {
    return 'No events found for this run.';
  }

  let output = `# Timeline (${events.length} events)\n\n`;

  events.forEach((event, index) => {
    const time = new Date(event.timestamp).toISOString();
    output += `${index + 1}. **${event.event_type}** (${time})\n`;

    // Extract key data fields
    if (event.data) {
      if (event.data.model) {
        output += `   Model: ${event.data.model}\n`;
      }
      if (event.data.latency_ms) {
        output += `   Latency: ${event.data.latency_ms}ms\n`;
      }
      if (event.data.cost) {
        output += `   Cost: $${Number(event.data.cost).toFixed(6)}\n`;
      }
      if (event.data.tokens_in && event.data.tokens_out) {
        output += `   Tokens: ${event.data.tokens_in} in, ${event.data.tokens_out} out\n`;
      }

      // For LLM calls, include prompts and completions
      if (event.event_type === 'llm_call') {
        if (event.data.system_prompt) {
          output += `\n   **System Prompt:**\n   ${event.data.system_prompt.substring(0, 500)}${event.data.system_prompt.length > 500 ? '...' : ''}\n`;
        }
        if (event.data.prompt) {
          output += `\n   **Prompt:**\n   ${event.data.prompt.substring(0, 500)}${event.data.prompt.length > 500 ? '...' : ''}\n`;
        }
        if (event.data.completion) {
          output += `\n   **Completion:**\n   ${event.data.completion.substring(0, 500)}${event.data.completion.length > 500 ? '...' : ''}\n`;
        }
      }

      // For tool calls, show input/output
      if (event.event_type === 'tool_call') {
        if (event.data.tool_input) {
          output += `\n   **Tool Input:**\n   ${JSON.stringify(event.data.tool_input).substring(0, 300)}${JSON.stringify(event.data.tool_input).length > 300 ? '...' : ''}\n`;
        }
        if (event.data.tool_output) {
          output += `\n   **Tool Output:**\n   ${JSON.stringify(event.data.tool_output).substring(0, 300)}${JSON.stringify(event.data.tool_output).length > 300 ? '...' : ''}\n`;
        }
      }
    }

    output += `\n`;
  });

  return output;
}

/**
 * Build execution tree from events
 */
interface TreeNode {
  event: Event;
  children: TreeNode[];
}

function buildTree(events: Event[]): TreeNode[] {
  const eventMap = new Map<string, TreeNode>();
  const roots: TreeNode[] = [];

  // Create nodes
  events.forEach(event => {
    eventMap.set(event.event_id, { event, children: [] });
  });

  // Build tree structure
  events.forEach(event => {
    const node = eventMap.get(event.event_id)!;

    if (event.parent_event_id && eventMap.has(event.parent_event_id)) {
      // Add as child to parent
      const parent = eventMap.get(event.parent_event_id)!;
      parent.children.push(node);
    } else {
      // Root node
      roots.push(node);
    }
  });

  return roots;
}

function formatTreeNode(node: TreeNode, depth: number = 0): string {
  const indent = '  '.repeat(depth);
  const event = node.event;
  const time = new Date(event.timestamp).toISOString().split('T')[1].split('.')[0];

  let output = `${indent}├─ [${time}] ${event.event_type}`;

  // Add key metrics
  if (event.data) {
    const parts: string[] = [];
    if (event.data.model) parts.push(`model: ${event.data.model}`);
    if (event.data.latency_ms) parts.push(`${event.data.latency_ms}ms`);
    if (event.data.cost) parts.push(`$${Number(event.data.cost).toFixed(6)}`);

    if (parts.length > 0) {
      output += ` (${parts.join(', ')})`;
    }
  }

  output += '\n';

  // Recursively format children
  node.children.forEach(child => {
    output += formatTreeNode(child, depth + 1);
  });

  return output;
}

/**
 * Format execution trace as tree for LLM consumption
 */
export function formatExecutionTrace(events: Event[]): string {
  if (events.length === 0) {
    return 'No events found for this run.';
  }

  const tree = buildTree(events);

  let output = `# Execution Trace (${events.length} events)\n\n`;
  output += '```\n';

  tree.forEach(root => {
    output += formatTreeNode(root);
  });

  output += '```\n';

  return output;
}

/**
 * Format comparison table for multiple runs
 */
export function formatRunComparison(runs: RunDetails[]): string {
  if (runs.length === 0) {
    return 'No runs to compare.';
  }

  let output = `# Run Comparison (${runs.length} runs)\n\n`;

  output += '| Run Name | Status | Duration | Cost | Tokens In | Tokens Out | Events |\n';
  output += '|----------|--------|----------|------|-----------|------------|--------|\n';

  runs.forEach(run => {
    const duration = run.total_duration_ms ? `${run.total_duration_ms.toFixed(0)}ms` : 'N/A';
    const cost = run.total_cost ? `$${Number(run.total_cost).toFixed(4)}` : 'N/A';

    output += `| ${run.run_name} | ${run.status} | ${duration} | ${cost} | ${run.tokens_in || 0} | ${run.tokens_out || 0} | ${run.event_count} |\n`;
  });

  output += '\n';

  // Add insights
  if (runs.length > 1) {
    const costs = runs.map(r => r.total_cost || 0);
    const maxCost = Math.max(...costs);
    const minCost = Math.min(...costs.filter(c => c > 0));
    const avgCost = costs.reduce((a, b) => a + b, 0) / costs.length;

    output += '## Insights\n\n';
    output += `- **Average Cost:** $${avgCost.toFixed(4)}\n`;
    output += `- **Cost Range:** $${minCost.toFixed(4)} - $${maxCost.toFixed(4)}\n`;

    const mostExpensive = runs.find(r => r.total_cost === maxCost);
    const cheapest = runs.find(r => r.total_cost === minCost);

    if (mostExpensive && cheapest && mostExpensive !== cheapest) {
      const diff = ((maxCost - minCost) / minCost * 100).toFixed(1);
      output += `- **Most Expensive:** ${mostExpensive.run_name} ($${maxCost.toFixed(4)})\n`;
      output += `- **Cheapest:** ${cheapest.run_name} ($${minCost.toFixed(4)})\n`;
      output += `- **Difference:** ${diff}% more expensive\n`;
    }
  }

  return output;
}

/**
 * Format cost breakdown for LLM consumption
 */
export function formatCostBreakdown(breakdown: any[]): string {
  if (breakdown.length === 0) {
    return 'No cost data available.';
  }

  let output = `# Cost Breakdown by Model\n\n`;

  output += '| Model | Calls | Total Cost | Tokens In | Tokens Out | Avg Latency |\n';
  output += '|-------|-------|------------|-----------|------------|-------------|\n';

  let totalCost = 0;
  let totalCalls = 0;

  breakdown.forEach(item => {
    const cost = Number(item.total_cost || 0);
    const calls = Number(item.call_count || 0);
    const tokensIn = Number(item.total_tokens_in || 0);
    const tokensOut = Number(item.total_tokens_out || 0);
    const latency = Number(item.avg_latency_ms || 0);

    totalCost += cost;
    totalCalls += calls;

    output += `| ${item.model || 'unknown'} | ${calls} | $${cost.toFixed(4)} | ${tokensIn} | ${tokensOut} | ${latency.toFixed(0)}ms |\n`;
  });

  output += '\n';
  output += `**Total:** ${totalCalls} calls, $${totalCost.toFixed(4)}\n`;

  return output;
}

/**
 * Format global metrics for LLM consumption
 */
export function formatGlobalMetrics(metrics: any): string {
  let output = `# Global Metrics\n\n`;

  output += `## Overview\n\n`;
  output += `- **Total Agents:** ${metrics.total_agents}\n`;
  output += `- **Total Runs:** ${metrics.total_runs}\n`;
  output += `- **Total Events:** ${metrics.total_events}\n`;
  output += `- **Total Duration:** ${Number(metrics.total_duration_hours).toFixed(2)} hours\n\n`;

  output += `## Costs\n\n`;
  output += `- **Total Cost:** $${Number(metrics.total_cost).toFixed(4)}\n`;
  output += `- **Average Cost per Run:** $${Number(metrics.avg_cost_per_run).toFixed(4)}\n\n`;

  output += `## Tokens\n\n`;
  output += `- **Total Input Tokens:** ${Number(metrics.total_tokens_in).toLocaleString()}\n`;
  output += `- **Total Output Tokens:** ${Number(metrics.total_tokens_out).toLocaleString()}\n`;
  output += `- **Total Tokens:** ${(Number(metrics.total_tokens_in) + Number(metrics.total_tokens_out)).toLocaleString()}\n`;

  return output;
}
