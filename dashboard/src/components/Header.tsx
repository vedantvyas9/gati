import { Link } from 'react-router-dom'

interface HeaderProps {
  isDarkMode: boolean
  onToggleDarkMode: () => void
}

export default function Header({ isDarkMode, onToggleDarkMode }: HeaderProps) {
  return (
    <header className="bg-navy-500 dark:bg-navy-900 text-white shadow-lg">
      <div className="container mx-auto px-4 py-6">
        <div className="flex items-center justify-between">
          <Link to="/" className="flex items-center space-x-2 hover:opacity-80 transition-opacity">
            <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center font-bold text-navy-500">
              G
            </div>
            <h1 className="text-2xl font-serif font-bold">GATI</h1>
          </Link>

          <nav className="flex items-center space-x-6">
            <Link
              to="/"
              className="hover:text-white/80 transition-colors font-medium"
            >
              Agents
            </Link>
            <Link
              to="/metrics"
              className="hover:text-white/80 transition-colors font-medium"
            >
              Metrics
            </Link>

            <button
              onClick={onToggleDarkMode}
              className="p-2 rounded-lg hover:bg-white/10 transition-colors"
              title="Toggle dark mode"
            >
              {isDarkMode ? (
                <svg
                  className="w-5 h-5"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fillRule="evenodd"
                    d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l-2.12-2.12a1 1 0 011.414-1.414l2.12 2.12a1 1 0 01-1.414 1.414zM2.05 6.464L4.17 4.343a1 1 0 011.414 1.414L3.464 7.878a1 1 0 11-1.414-1.414zM17.95 6.464a1 1 0 001.414-1.414L16.828 2.05a1 1 0 00-1.414 1.414l2.12 2.12z"
                    clipRule="evenodd"
                  />
                </svg>
              ) : (
                <svg
                  className="w-5 h-5"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
                </svg>
              )}
            </button>
          </nav>
        </div>
      </div>
    </header>
  )
}
