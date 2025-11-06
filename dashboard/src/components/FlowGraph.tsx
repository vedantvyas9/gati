import { useCallback, useMemo } from 'react'
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  MiniMap,
  ReactFlowProvider,
  MarkerType,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { ExecutionTreeNodeResponse } from '../types'

interface FlowGraphProps {
  nodes: ExecutionTreeNodeResponse[]
  onNodeSelect?: (node: ExecutionTreeNodeResponse) => void
  selectedNodeId?: string
}

// Color mapping for event types
const EVENT_TYPE_COLORS: Record<string, { bg: string; border: string }> = {
  llm_call: {
    bg: '#DBEAFE',
    border: '#3B82F6',
  },
  tool_call: {
    bg: '#DCFCE7',
    border: '#16A34A',
  },
  agent_start: {
    bg: '#FED7AA',
    border: '#EA580C',
  },
  agent_end: {
    bg: '#FED7AA',
    border: '#EA580C',
  },
  chain_start: {
    bg: '#FED7AA',
    border: '#EA580C',
  },
  chain_end: {
    bg: '#FED7AA',
    border: '#EA580C',
  },
  error: {
    bg: '#FEE2E2',
    border: '#DC2626',
  },
}

function getEventTypeColor(eventType: string) {
  return EVENT_TYPE_COLORS[eventType] || {
    bg: '#F3F4F6',
    border: '#9CA3AF',
  }
}

// Shared function to get node display name - matches ExecutionTree logic
function getNodeDisplayName(node: ExecutionTreeNodeResponse): string {
  const data = node.data as any

  // Priority order for specific event types
  // For tool_call: prioritize tool_name
  if (node.event_type === 'tool_call') {
    if (data?.tool_name && typeof data.tool_name === 'string' && data.tool_name.trim()) {
      return String(data.tool_name)
    }
    if (data?.tool && typeof data.tool === 'string' && data.tool.trim()) {
      return String(data.tool)
    }
  }

  // For node_execution: prioritize node_name
  if (node.event_type === 'node_execution') {
    if (data?.node_name && typeof data.node_name === 'string' && data.node_name.trim()) {
      return String(data.node_name)
    }
  }

  // General priority order: name > tool_name > tool > function_name > function > node_name > model
  if (data?.name && typeof data.name === 'string' && data.name.trim()) {
    return String(data.name)
  }

  if (data?.tool_name && typeof data.tool_name === 'string' && data.tool_name.trim()) {
    return String(data.tool_name)
  }

  if (data?.tool && typeof data.tool === 'string' && data.tool.trim()) {
    return String(data.tool)
  }

  if (data?.function_name && typeof data.function_name === 'string' && data.function_name.trim()) {
    return String(data.function_name)
  }

  if (data?.function && typeof data.function === 'string' && data.function.trim()) {
    return String(data.function)
  }

  if (data?.node_name && typeof data.node_name === 'string' && data.node_name.trim()) {
    return String(data.node_name)
  }

  if (data?.model && typeof data.model === 'string' && data.model.trim()) {
    return String(data.model)
  }

  // Fallback: try to extract from relevant fields, excluding metadata, status, and ID fields
  if (node.event_type === 'node_execution' || node.event_type === 'tool_call') {
    const keys = Object.keys(data || {}).filter(k =>
      !['timestamp', 'event_id', 'run_id', 'agent_name', 'created_at', 'updated_at',
        'status', 'completed', 'success', 'error', 'result', 'output', 'input',
        'parent_event_id', 'latency_ms', 'duration_ms', 'cost', 'tokens_in', 'tokens_out'].includes(k)
    )

    // Look for string values that look like names
    for (const key of keys) {
      const value = data[key]
      if (typeof value === 'string' &&
          value.trim() &&
          value.length < 100 &&
          value.length > 0 &&
          !value.startsWith('{') &&
          !value.startsWith('[') &&
          !value.includes('uuid') &&
          !/^[a-f0-9-]{36}$/.test(value)) { // Exclude UUIDs
        return String(value)
      }
    }
  }

  // Fallback to event type
  const labels: Record<string, string> = {
    llm_call: 'LLM Call',
    tool_call: 'Tool Call',
    agent_start: 'Agent Start',
    agent_end: 'Agent End',
    chain_start: 'Chain Start',
    chain_end: 'Chain End',
    node_execution: 'Node Execution',
  }
  return labels[node.event_type] || node.event_type.replace(/_/g, ' ')
}

function buildGraphFromTree(
  treeNodes: ExecutionTreeNodeResponse[]
): { nodes: Node[]; edges: Edge[]; nodeMap: Map<string, ExecutionTreeNodeResponse> } {
  const nodes: Node[] = []
  const edges: Edge[] = []
  const nodeMap = new Map<string, ExecutionTreeNodeResponse>()

  function processNode(
    node: ExecutionTreeNodeResponse,
    xPos: number,
    yPos: number,
    parentId: string | null,
    depth: number
  ): number {
    const colors = getEventTypeColor(node.event_type || 'unknown')

    // Use the same naming logic as ExecutionTree
    const displayLabel = getNodeDisplayName(node)

    nodes.push({
      id: node.event_id,
      data: {
        label: (
          <div className="text-xs font-mono max-w-xs">
            <div className="font-bold mb-1">{displayLabel as unknown as React.ReactNode}</div>
            <div className="text-gray-600">
              {node.latency_ms !== undefined && node.latency_ms !== null
                ? `${(node.latency_ms / 1000).toFixed(2)}s`
                : '—'}
            </div>
            {node.cost !== undefined && node.cost !== null ? (
              <div className="text-green-700 font-semibold">
                ${node.cost.toFixed(4)}
              </div>
            ) : null}
          </div>
        ) as unknown as React.ReactNode,
      },
      position: { x: xPos, y: yPos },
      style: {
        background: colors.bg,
        border: `2px solid ${colors.border}`,
        borderRadius: '8px',
        padding: '8px',
        minWidth: '120px',
        minHeight: '60px',
      },
    })

    nodeMap.set(node.event_id, node)

    // Create edge from parent
    if (parentId) {
      edges.push({
        id: `${parentId}-${node.event_id}`,
        source: parentId,
        target: node.event_id,
        animated: true,
        style: {
          stroke: '#999',
          strokeWidth: 2,
        },
        markerEnd: { type: MarkerType.ArrowClosed, color: '#999' },
      })
    }

    // Process children - vertical layout with proper spacing
    if (node.children && node.children.length > 0) {
      const numChildren = node.children.length
      const childSpacing = 200
      const totalWidth = (numChildren - 1) * childSpacing
      const startX = xPos - totalWidth / 2

      node.children.forEach((child, index) => {
        const childX = startX + index * childSpacing
        const childY = yPos + 150
        processNode(child, childX, childY, node.event_id, depth + 1)
      })
    }

    return depth
  }

  // Improved layout: Process tree structure while enforcing agent_start at top, agent_end at bottom
  // First pass: process all nodes to understand structure
  treeNodes.forEach((node, index) => {
    let yPos = 0

    // Determine Y position based on node type
    if (node.event_type === 'agent_start') {
      yPos = 0  // Top
    } else if (node.event_type === 'agent_end') {
      yPos = 400  // Bottom
    } else {
      // Middle - but check if it's a child of agent_start
      yPos = 200
    }

    const xPos = index * 250
    processNode(node, xPos, yPos, null, 0)
  })

  return { nodes, edges, nodeMap }
}

function FlowGraphInner({
  nodes: treeNodes,
  onNodeSelect,
  selectedNodeId,
}: FlowGraphProps) {
  const { nodes: graphNodes, edges: graphEdges, nodeMap } = useMemo(
    () => buildGraphFromTree(treeNodes),
    [treeNodes]
  )

  const [nodes, setNodes, onNodesChange] = useNodesState(graphNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(graphEdges)

  // Highlight selected node
  const selectedNodes = useMemo(() => {
    return nodes.map((node) => ({
      ...node,
      style: {
        ...node.style,
        border:
          node.id === selectedNodeId
            ? `3px solid #0F172A`
            : (node.style as any)?.border,
        boxShadow:
          node.id === selectedNodeId ? '0 0 0 4px rgba(15, 23, 42, 0.3)' : 'none',
      },
    }))
  }, [nodes, selectedNodeId])

  const onNodeClick = useCallback(
    (_: unknown, node: Node) => {
      const treeNode = nodeMap.get(node.id)
      if (treeNode) {
        onNodeSelect?.(treeNode)
      }
    },
    [nodeMap, onNodeSelect]
  )

  if (!treeNodes || treeNodes.length === 0) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-gray-50 dark:bg-gray-900 rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-700">
        <p className="text-gray-600 dark:text-gray-400">
          No execution events to display
        </p>
      </div>
    )
  }

  return (
    <div className="w-full h-full">
      <ReactFlow
        nodes={selectedNodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        fitView
      >
        <Background color="#aaa" gap={16} />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  )
}

export default function FlowGraph(props: FlowGraphProps) {
  return (
    <ReactFlowProvider>
      <FlowGraphInner {...props} />
    </ReactFlowProvider>
  )
}
