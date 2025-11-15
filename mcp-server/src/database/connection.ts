/**
 * Database connection for SQLite
 */
import Database from 'better-sqlite3';
import { GatiMCPConfig } from '../config/config.js';

let db: Database.Database | null = null;

/**
 * Initialize database connection
 */
export function initializeDatabase(config: GatiMCPConfig): Database.Database {
  if (db) {
    return db;
  }

  db = new Database(config.databasePath, {
    readonly: true, // MCP server only reads data
    fileMustExist: true,
  });

  // Enable WAL mode for better concurrency
  db.pragma('journal_mode = WAL');

  return db;
}

/**
 * Get database instance
 */
export function getDatabase(): Database.Database {
  if (!db) {
    throw new Error('Database not initialized. Call initializeDatabase first.');
  }
  return db;
}

/**
 * Close database connection
 */
export function closeDatabase(): void {
  if (db) {
    db.close();
    db = null;
  }
}

/**
 * Test database connection
 */
export function testConnection(): boolean {
  try {
    const result = getDatabase().prepare('SELECT 1').get();
    return true;
  } catch (error) {
    console.error('Database connection test failed:', error);
    return false;
  }
}
