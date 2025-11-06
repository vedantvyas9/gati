import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Agent } from '../types'
import { apiClient } from '../services/api'
import ConfirmationModal from './ConfirmationModal'

interface AgentCardProps {
  agent: Agent
  onDelete?: (agentName: string) => void
}

export default function AgentCard({ agent, onDelete }: AgentCardProps) {
  const totalRuns = agent.total_runs || 0
  const totalCost = agent.total_cost || 0
  const tokensUsed = (agent.total_events || 0) * 100 // Rough estimate
  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [isDeleting, setIsDeleting] = useState(false)

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setShowDeleteModal(true)
  }

  const handleConfirmDelete = async () => {
    try {
      setIsDeleting(true)
      await apiClient.deleteAgent(agent.name)
      setShowDeleteModal(false)
      onDelete?.(agent.name)
    } catch (error) {
      console.error('Failed to delete agent:', error)
      alert('Failed to delete agent. Please try again.')
    } finally {
      setIsDeleting(false)
    }
  }

  return (
    <>
      <Link to={`/agents/${agent.name}`}>
        <div className="card hover:shadow-lg dark:hover:shadow-2xl transition-shadow cursor-pointer h-full">
          <div className="flex flex-col h-full">
            <div className="flex items-start justify-between mb-4">
              <div className="flex-1">
                <h3 className="text-xl font-serif font-bold text-navy-900 dark:text-white mb-1">
                  {agent.name}
                </h3>
                {agent.description && (
                  <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-2">
                    {agent.description}
                  </p>
                )}
              </div>
              <div className="flex-shrink-0 w-10 h-10 bg-navy-100 dark:bg-navy-800 rounded-lg flex items-center justify-center">
                <span className="text-navy-600 dark:text-navy-300 font-bold">
                  {agent.name.charAt(0).toUpperCase()}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4 mt-auto pt-4 border-t border-gray-200 dark:border-gray-700">
              <div>
                <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">Runs</p>
                <p className="text-lg font-bold text-navy-600 dark:text-navy-400">
                  {totalRuns}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">Cost</p>
                <p className="text-lg font-bold text-navy-600 dark:text-navy-400">
                  ${totalCost.toFixed(2)}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-600 dark:text-gray-400 mb-1">Tokens</p>
                <p className="text-lg font-bold text-navy-600 dark:text-navy-400">
                  {(tokensUsed / 1000).toFixed(0)}K
                </p>
              </div>
            </div>

            {agent.created_at && (
              <p className="text-xs text-gray-500 dark:text-gray-500 mt-3">
                Created {new Date(agent.created_at).toLocaleDateString()}
              </p>
            )}

            <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700 flex gap-2">
              <button
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                }}
                className="flex-1 px-3 py-2 text-sm bg-navy-50 dark:bg-navy-900/50 text-navy-600 dark:text-navy-300 rounded hover:bg-navy-100 dark:hover:bg-navy-900 transition-colors font-medium"
              >
                View Details
              </button>
              <button
                onClick={handleDeleteClick}
                className="px-3 py-2 text-sm bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 rounded hover:bg-red-100 dark:hover:bg-red-900/40 transition-colors font-medium"
                title="Delete agent"
              >
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                  />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </Link>

      <ConfirmationModal
        isOpen={showDeleteModal}
        title="Delete Agent"
        message={`Are you sure? This action cannot be undone. All runs and events for "${agent.name}" will be permanently deleted.`}
        confirmText="Delete"
        cancelText="Cancel"
        isDangerous
        isLoading={isDeleting}
        onConfirm={handleConfirmDelete}
        onCancel={() => setShowDeleteModal(false)}
      />
    </>
  )
}
