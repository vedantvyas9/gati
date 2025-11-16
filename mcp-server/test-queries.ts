import { initializeDatabase, closeDatabase } from './src/database/connection.js';
import { listAgents } from './src/database/queries.js';

// Set database path
process.env.DATABASE_PATH = '/Users/vedantvyas/Desktop/GATI/gati-sdk/backend/gati.db';

// Initialize database
initializeDatabase({ databasePath: process.env.DATABASE_PATH });

// Test query
try {
  const agents = listAgents();
  console.log('=== AGENTS FOUND ===');
  console.log(JSON.stringify(agents, null, 2));
  console.log(`\nTotal agents: ${agents.length}`);
} catch (error) {
  console.error('Error querying agents:', error);
} finally {
  closeDatabase();
}
