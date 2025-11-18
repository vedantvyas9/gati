// Vercel Serverless Function for GATI Telemetry
// Deploy to: https://your-project.vercel.app/api/metrics

const { Pool } = require('pg');
const { URL } = require('url');

if (!process.env.POSTGRES_URL) {
  throw new Error('POSTGRES_URL environment variable is not configured');
}

const dbUrl = new URL(process.env.POSTGRES_URL);

const pool = new Pool({
  host: dbUrl.hostname,
  port: parseInt(dbUrl.port, 10),
  database: dbUrl.pathname.split('/')[1],
  user: dbUrl.username,
  password: dbUrl.password,
  ssl: {
    rejectUnauthorized: false,
  },
});

async function withTransaction(callback) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    const result = await callback(client);
    await client.query('COMMIT');
    return result;
  } catch (error) {
    await client.query('ROLLBACK');
    throw error;
  } finally {
    client.release();
  }
}

module.exports = async function handler(request, response) {
  // Set CORS headers
  response.setHeader('Access-Control-Allow-Origin', '*');
  response.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  response.setHeader(
    'Access-Control-Allow-Headers',
    'Content-Type, User-Agent, X-API-Key, Authorization'
  );

  // Handle preflight
  if (request.method === 'OPTIONS') {
    return response.status(200).end();
  }

  // Only accept POST
  if (request.method !== 'POST') {
    return response.status(405).json({ error: 'Method not allowed' });
  }

  // Verify API token (optional for anonymous telemetry)
  const apiToken = request.headers['x-api-key'] || request.headers['authorization']?.replace('Bearer ', '');

  // Validate token against database if provided
  let userEmail = null;
  if (apiToken) {
    try {
      const userResult = await pool.query(
        'SELECT email FROM gati_users WHERE api_token = $1',
        [apiToken]
      );

      if (userResult.rows.length === 0) {
        return response.status(401).json({ error: 'Unauthorized - Invalid API token' });
      }

      userEmail = userResult.rows[0].email;

      await pool.query('UPDATE gati_users SET last_active = NOW() WHERE api_token = $1', [
        apiToken,
      ]);
    } catch (error) {
      console.error('Token validation error:', error);
      return response.status(500).json({ error: 'Authentication error' });
    }
  }

  try {
    const {
      installation_id,
      user_email,
      sdk_version,
      agents_tracked,
      events_today,
      lifetime_events,
      mcp_queries,
      frameworks_detected,
      timestamp
    } = request.body;

    // Validate required fields
    if (
      !installation_id ||
      !sdk_version ||
      agents_tracked === undefined ||
      events_today === undefined ||
      lifetime_events === undefined ||
      frameworks_detected === undefined ||
      !timestamp
    ) {
      return response.status(400).json({
        error: 'Missing required fields',
        required: [
          'installation_id',
          'sdk_version',
          'agents_tracked',
          'events_today',
          'lifetime_events',
          'frameworks_detected',
          'timestamp',
        ],
      });
    }

    if (!Array.isArray(frameworks_detected)) {
      return response.status(400).json({ error: 'frameworks_detected must be an array' });
    }

    const numericAgents = Number(agents_tracked);
    const numericEventsToday = Number(events_today);
    const numericLifetimeEvents = Number(lifetime_events);
    const numericMcpQueries = mcp_queries === undefined ? 0 : Number(mcp_queries);

    if (
      !Number.isInteger(numericAgents) ||
      !Number.isInteger(numericEventsToday) ||
      !Number.isInteger(numericLifetimeEvents) ||
      !Number.isInteger(numericMcpQueries) ||
      numericAgents < 0 ||
      numericEventsToday < 0 ||
      numericLifetimeEvents < 0 ||
      numericMcpQueries < 0
    ) {
      return response.status(400).json({
        error: 'Invalid numeric fields',
      });
    }

    const timestampDate = new Date(timestamp);
    if (Number.isNaN(timestampDate.getTime())) {
      return response.status(400).json({ error: 'Invalid timestamp format' });
    }

    const frameworksJson = JSON.stringify(frameworks_detected);
    const effectiveEmail = userEmail || user_email || null;

    await withTransaction(async (client) => {
      await client.query(
        `INSERT INTO gati_metrics (
          installation_id,
          user_email,
          sdk_version,
          agents_tracked,
          events_today,
          lifetime_events,
          mcp_queries,
          frameworks_detected
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (installation_id) DO UPDATE SET
          user_email = EXCLUDED.user_email,
          sdk_version = EXCLUDED.sdk_version,
          agents_tracked = EXCLUDED.agents_tracked,
          events_today = EXCLUDED.events_today,
          lifetime_events = EXCLUDED.lifetime_events,
          mcp_queries = EXCLUDED.mcp_queries,
          frameworks_detected = EXCLUDED.frameworks_detected,
          last_updated = NOW()`,
        [
          installation_id,
          effectiveEmail,
          sdk_version,
          numericAgents,
          numericEventsToday,
          numericLifetimeEvents,
          numericMcpQueries,
          frameworksJson,
        ]
      );

      await client.query(
        `INSERT INTO gati_metrics_snapshots (
          installation_id,
          user_email,
          sdk_version,
          agents_tracked,
          events_today,
          lifetime_events,
          mcp_queries,
          frameworks_detected,
          timestamp
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)`,
        [
          installation_id,
          effectiveEmail,
          sdk_version,
          numericAgents,
          numericEventsToday,
          numericLifetimeEvents,
          numericMcpQueries,
          frameworksJson,
          timestampDate.toISOString(),
        ]
      );
    });

    return response.status(200).json({
      status: 'success',
      installation_id,
      snapshot_recorded: true,
    });
  } catch (error) {
    console.error('Error processing metrics:', error);
    return response.status(500).json({
      error: 'Internal server error',
      message: error.message
    });
  }
}
