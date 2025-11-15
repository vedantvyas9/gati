/**
 * Configuration management for GATI MCP Server
 */

export interface GatiMCPConfig {
  databasePath: string;
}

/**
 * Load configuration from environment variables
 */
export function loadConfig(): GatiMCPConfig {
  const databasePath = process.env.DATABASE_PATH || './gati.db';

  return {
    databasePath,
  };
}

/**
 * Validate configuration
 */
export function validateConfig(config: GatiMCPConfig): void {
  if (!config.databasePath) {
    throw new Error('DATABASE_PATH is required');
  }
}
