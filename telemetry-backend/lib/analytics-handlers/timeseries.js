// Timeseries handler
const pool = require('../../api/analytics/db');

function normalizeDate(value) {
  if (!value) return null;
  if (value instanceof Date) {
    return new Date(value.getFullYear(), value.getMonth(), value.getDate());
  }
  if (typeof value === 'string') {
    const d = new Date(value);
    return new Date(d.getFullYear(), d.getMonth(), d.getDate());
  }
  return value;
}

function formatDate(date) {
  return date.toISOString().split('T')[0];
}

module.exports = async function handler(request, response) {
  try {
    const days = parseInt(request.query?.days || '30', 10);
    const utcNow = new Date();
    const endDate = new Date(utcNow.getFullYear(), utcNow.getMonth(), utcNow.getDate());

    let startDate;
    if (days > 0) {
      startDate = new Date(endDate);
      startDate.setDate(startDate.getDate() - (days - 1));
    } else {
      const earliestResult = await pool.query('SELECT MIN(recorded_at) as earliest FROM public.gati_metrics_snapshots');
      const earliest = earliestResult.rows[0]?.earliest;
      if (earliest) {
        startDate = normalizeDate(earliest);
      } else {
        startDate = new Date(endDate);
        startDate.setDate(startDate.getDate() - 29);
      }
    }

    if (startDate > endDate) startDate = endDate;

    const summaryResult = await pool.query(`
      SELECT COUNT(DISTINCT installation_id) as total_installations,
             COALESCE(SUM(lifetime_events), 0) as total_events,
             COALESCE(SUM(agents_tracked), 0) as total_agents,
             COALESCE(SUM(mcp_queries), 0) as total_mcp_queries
      FROM public.gati_metrics
    `);
    const summaryRow = summaryResult.rows[0];
    const usersResult = await pool.query('SELECT COUNT(*) as count FROM public.gati_users');
    const totalUsers = parseInt(usersResult.rows[0]?.count || 0);

    const activeWindowStart = new Date(utcNow);
    activeWindowStart.setDate(activeWindowStart.getDate() - 7);
    const activeResult = await pool.query(
      `SELECT COUNT(DISTINCT installation_id) as count FROM public.gati_metrics_snapshots WHERE recorded_at >= $1`,
      [activeWindowStart]
    );
    const activeInstallations = parseInt(activeResult.rows[0]?.count || 0);

    const timeseriesResult = await pool.query(
      `SELECT DATE(recorded_at) as bucket_date,
              COUNT(DISTINCT installation_id) as daily_active_installations,
              COUNT(DISTINCT user_email) as active_users,
              COALESCE(SUM(events_today), 0) as events_per_day,
              COALESCE(SUM(agents_tracked), 0) as agents_tracked,
              COALESCE(SUM(mcp_queries), 0) as mcp_queries
       FROM public.gati_metrics_snapshots
       WHERE recorded_at >= $1
       GROUP BY DATE(recorded_at)
       ORDER BY DATE(recorded_at)`,
      [startDate]
    );

    const dailyMetrics = {};
    timeseriesResult.rows.forEach((row) => {
      const bucket = normalizeDate(row.bucket_date);
      if (bucket) {
        dailyMetrics[formatDate(bucket)] = {
          daily_active_installations: parseInt(row.daily_active_installations || 0),
          active_users: parseInt(row.active_users || 0),
          events_per_day: parseInt(row.events_per_day || 0),
          agents_tracked: parseInt(row.agents_tracked || 0),
          mcp_queries: parseInt(row.mcp_queries || 0),
        };
      }
    });

    const firstSeenResult = await pool.query(`
      SELECT installation_id, MIN(recorded_at) as first_seen_at
      FROM public.gati_metrics_snapshots
      WHERE installation_id IS NOT NULL
      GROUP BY installation_id
    `);

    const initialTotalResult = await pool.query(
      `SELECT COUNT(*) as count FROM (
        SELECT installation_id, MIN(recorded_at) as first_seen_at
        FROM public.gati_metrics_snapshots
        WHERE installation_id IS NOT NULL
        GROUP BY installation_id
      ) subq WHERE first_seen_at < $1`,
      [startDate]
    );
    let initialCumulative = parseInt(initialTotalResult.rows[0]?.count || 0);

    const dailyNewResult = await pool.query(
      `SELECT DATE(first_seen_at) as first_seen_date, COUNT(*) as new_installations
       FROM (SELECT installation_id, MIN(recorded_at) as first_seen_at
             FROM public.gati_metrics_snapshots
             WHERE installation_id IS NOT NULL
             GROUP BY installation_id) subq
       WHERE first_seen_at >= $1
       GROUP BY DATE(first_seen_at)
       ORDER BY DATE(first_seen_at)`,
      [startDate]
    );

    const dailyNew = {};
    dailyNewResult.rows.forEach((row) => {
      const date = normalizeDate(row.first_seen_date);
      if (date) {
        dailyNew[formatDate(date)] = parseInt(row.new_installations || 0);
      }
    });

    const series = [];
    let cumulativeInstallations = initialCumulative;
    const currentDate = new Date(startDate);
    while (currentDate <= endDate) {
      const dateStr = formatDate(currentDate);
      const metrics = dailyMetrics[dateStr] || {
        daily_active_installations: 0, active_users: 0, events_per_day: 0,
        agents_tracked: 0, mcp_queries: 0,
      };
      const newInstallations = dailyNew[dateStr] || 0;
      cumulativeInstallations += newInstallations;
      series.push({
        date: dateStr,
        daily_active_installations: metrics.daily_active_installations,
        cumulative_installations: cumulativeInstallations,
        total_events_per_day: metrics.events_per_day,
        active_users: metrics.active_users,
        agents_tracked: metrics.agents_tracked,
        mcp_queries: metrics.mcp_queries,
      });
      currentDate.setDate(currentDate.getDate() + 1);
    }

    let growthRateMom = null;
    if (series.length >= 30) {
      const currentMonthEvents = series.slice(-30).reduce((sum, s) => sum + s.total_events_per_day, 0);
      if (series.length >= 60) {
        const previousMonthEvents = series.slice(-60, -30).reduce((sum, s) => sum + s.total_events_per_day, 0);
        if (previousMonthEvents > 0) {
          growthRateMom = ((currentMonthEvents - previousMonthEvents) / previousMonthEvents) * 100;
        }
      }
    }

    const authResult = await pool.query(
      'SELECT COUNT(DISTINCT installation_id) as count FROM public.gati_metrics WHERE user_email IS NOT NULL'
    );
    const authenticatedCount = parseInt(authResult.rows[0]?.count || 0);
    const totalInstallations = parseInt(summaryRow.total_installations || 0);
    const anonymousCount = totalInstallations - authenticatedCount;

    const generatedAt = new Date();
    generatedAt.setMilliseconds(0);

    return response.status(200).json({
      summary: {
        total_installations: totalInstallations,
        active_installations: activeInstallations,
        total_users: totalUsers,
        total_events: parseInt(summaryRow.total_events || 0),
        total_agents: parseInt(summaryRow.total_agents || 0),
        total_mcp_queries: parseInt(summaryRow.total_mcp_queries || 0),
      },
      range: {
        days: days > 0 ? days : null,
        start_date: formatDate(startDate),
        end_date: formatDate(endDate),
      },
      generated_at: generatedAt.toISOString().replace(/\.\d{3}/, '') + 'Z',
      timeseries: series,
      growth_rate_mom: growthRateMom,
      authenticated_count: authenticatedCount,
      anonymous_count: anonymousCount,
    });
  } catch (error) {
    console.error('Error in analytics timeseries:', error);
    return response.status(500).json({ error: 'Internal server error', message: error.message });
  }
};
