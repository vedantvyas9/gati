/**
 * Telemetry client for MCP server
 *
 * Tracks anonymous usage metrics for the MCP server.
 * No sensitive data (queries, results, or PII) is collected.
 */

import { promises as fs } from 'fs';
import { homedir } from 'os';
import { join } from 'path';
import { randomUUID } from 'crypto';

interface TelemetryMetrics {
  installation_id: string;
  sdk_version: string;
  mcp_queries: number;
  agents_tracked: number;
  events_today: number;
  lifetime_events: number;
  frameworks_detected: string[];
  timestamp: string;
}

interface LocalMetrics {
  mcp_queries: number;
  last_reset_date: string;
}

export class TelemetryClient {
  private enabled: boolean;
  private endpoint: string;
  private sdkVersion: string;
  private installationId: string = '';
  private metrics: LocalMetrics = {
    mcp_queries: 0,
    last_reset_date: new Date().toISOString().split('T')[0],
  };

  private configDir: string;
  private metricsFile: string;
  private idFile: string;

  constructor(
    enabled: boolean = true,
    endpoint: string = process.env.GATI_TELEMETRY_URL || 'https://gati-mvp-telemetry.vercel.app/api/metrics',
    sdkVersion: string = '1.0.0'
  ) {
    this.enabled = enabled;
    this.endpoint = endpoint;
    this.sdkVersion = sdkVersion;

    // Set up paths - use same metrics.json as Python SDK
    this.configDir = join(homedir(), '.gati');
    this.metricsFile = join(this.configDir, 'metrics.json');
    this.idFile = join(this.configDir, '.gati_id');
  }

  /**
   * Initialize telemetry client
   */
  async init(): Promise<void> {
    if (!this.enabled) {
      return;
    }

    try {
      // Ensure config directory exists
      await fs.mkdir(this.configDir, { recursive: true });

      // Load or create installation ID
      this.installationId = await this.getOrCreateInstallationId();

      // Load metrics from disk
      await this.loadMetrics();

      console.error('[GATI Telemetry] Initialized');
    } catch (error) {
      console.error('[GATI Telemetry] Failed to initialize:', error);
    }
  }

  /**
   * Get or create installation ID
   */
  private async getOrCreateInstallationId(): Promise<string> {
    try {
      // Try to read existing ID
      const id = await fs.readFile(this.idFile, 'utf-8');
      return id.trim();
    } catch {
      // Create new ID
      const id = randomUUID();
      try {
        await fs.writeFile(this.idFile, id);
      } catch (error) {
        console.error('[GATI Telemetry] Failed to save installation ID:', error);
      }
      return id;
    }
  }

  /**
   * Load metrics from disk (shared with Python SDK)
   */
  private async loadMetrics(): Promise<void> {
    try {
      const data = await fs.readFile(this.metricsFile, 'utf-8');
      const loaded = JSON.parse(data);

      // Read mcp_queries from the shared metrics.json
      this.metrics.mcp_queries = loaded.mcp_queries || 0;
      this.metrics.last_reset_date =
        loaded.last_reset_date || new Date().toISOString().split('T')[0];
    } catch {
      // File doesn't exist or is invalid, use defaults
      this.metrics = {
        mcp_queries: 0,
        last_reset_date: new Date().toISOString().split('T')[0],
      };
    }
  }

  /**
   * Save metrics to disk (merge with existing metrics.json to preserve Python SDK data)
   */
  private async saveMetrics(): Promise<void> {
    try {
      // Read existing metrics.json to preserve other fields from Python SDK
      let existingData: any = {};
      try {
        const existing = await fs.readFile(this.metricsFile, 'utf-8');
        existingData = JSON.parse(existing);
      } catch {
        // File doesn't exist yet, that's okay - we'll create it
      }

      // Use the maximum of file value and in-memory value to handle race conditions
      const fileMcpQueries = existingData.mcp_queries || 0;
      const maxMcpQueries = Math.max(fileMcpQueries, this.metrics.mcp_queries);

      // Merge MCP queries into existing data (preserve all other fields)
      const merged = {
        ...existingData,
        mcp_queries: maxMcpQueries,
        last_reset_date: this.metrics.last_reset_date,
      };

      await fs.writeFile(this.metricsFile, JSON.stringify(merged, null, 2));
      
      // Update in-memory value to match what we saved
      this.metrics.mcp_queries = maxMcpQueries;
    } catch (error) {
      console.error('[GATI Telemetry] Failed to save metrics:', error);
    }
  }

  /**
   * Track an MCP query
   */
  async trackQuery(): Promise<void> {
    if (!this.enabled) {
      return;
    }

    // Reload from disk first to get the latest value (in case Python SDK updated it)
    await this.loadMetrics();

    this.metrics.mcp_queries++;

    // Save immediately so Python SDK can see the updated count
    await this.saveMetrics();
  }

  /**
   * Get current metrics (reads from shared metrics.json to include Python SDK data)
   */
  private async getMetrics(): Promise<TelemetryMetrics> {
    // Read the shared metrics.json to get agent and event counts from Python SDK
    let agentsTracked = 0;
    let eventsToday = 0;
    let lifetimeEvents = 0;
    let frameworksDetected: string[] = ['mcp'];

    try {
      const data = await fs.readFile(this.metricsFile, 'utf-8');
      const loaded = JSON.parse(data);
      
      agentsTracked = loaded.agents_tracked || loaded.legacy_agent_count || 0;
      eventsToday = loaded.events_today || 0;
      lifetimeEvents = loaded.lifetime_events || 0;
      
      // Merge frameworks (Python SDK might have detected others)
      if (Array.isArray(loaded.frameworks_detected)) {
        frameworksDetected = [...new Set([...frameworksDetected, ...loaded.frameworks_detected])];
      }
    } catch {
      // If we can't read the file, use defaults
    }

    return {
      installation_id: this.installationId,
      sdk_version: this.sdkVersion,
      mcp_queries: this.metrics.mcp_queries,
      agents_tracked: agentsTracked,
      events_today: eventsToday,
      lifetime_events: lifetimeEvents,
      frameworks_detected: frameworksDetected,
      timestamp: new Date().toISOString(),
    };
  }

  /**
   * Send metrics to telemetry endpoint
   */
  async sendMetrics(): Promise<void> {
    if (!this.enabled) {
      return;
    }

    try {
      const metrics = await this.getMetrics();

      const response = await fetch(this.endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'User-Agent': `gati-mcp-server/${this.sdkVersion}`,
        },
        body: JSON.stringify(metrics),
      });

      if (response.ok) {
        console.error('[GATI Telemetry] Metrics sent successfully');
      } else {
        console.error(
          `[GATI Telemetry] Failed to send metrics: ${response.status} ${response.statusText}`
        );
      }
    } catch (error) {
      console.error('[GATI Telemetry] Failed to send metrics:', error);
    }
  }

  /**
   * Shutdown telemetry client
   */
  async shutdown(): Promise<void> {
    if (!this.enabled) {
      return;
    }

    // Save final metrics
    await this.saveMetrics();

    // Send final telemetry
    await this.sendMetrics();

    console.error('[GATI Telemetry] Shutdown complete');
  }
}

// Global singleton instance
let telemetryClient: TelemetryClient | null = null;

/**
 * Initialize global telemetry client
 */
export async function initTelemetry(
  enabled: boolean = true,
  endpoint?: string
): Promise<void> {
  telemetryClient = new TelemetryClient(enabled, endpoint);
  await telemetryClient.init();

  // Send metrics every 2 minutes
  setInterval(async () => {
    await telemetryClient?.sendMetrics();
  }, 2 * 60 * 1000); // 2 minutes
}

/**
 * Track an MCP query
 */
export async function trackQuery(): Promise<void> {
  await telemetryClient?.trackQuery();
}

/**
 * Shutdown telemetry
 */
export async function shutdownTelemetry(): Promise<void> {
  await telemetryClient?.shutdown();
}
