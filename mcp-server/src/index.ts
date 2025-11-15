#!/usr/bin/env node

/**
 * GATI MCP Server
 *
 * Model Context Protocol server for querying GATI traces from AI assistants
 * like Claude Desktop and GitHub Copilot.
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';

import { loadConfig, validateConfig } from './config/config.js';
import { initializeDatabase, testConnection, closeDatabase } from './database/connection.js';
import { allTools } from './tools/tools.js';
import { initTelemetry, trackQuery, shutdownTelemetry } from './telemetry/client.js';

/**
 * Main server initialization
 */
async function main() {
  // Load and validate configuration
  const config = loadConfig();
  validateConfig(config);

  // Initialize database connection
  console.error('[GATI MCP] Initializing database connection...');
  initializeDatabase(config);

  // Test database connection
  const isConnected = testConnection();
  if (!isConnected) {
    console.error('[GATI MCP] Failed to connect to database. Please check your DATABASE_PATH.');
    process.exit(1);
  }

  console.error('[GATI MCP] Database connection successful');

  // Initialize telemetry (opt-in by default, can disable via env var)
  const telemetryEnabled = process.env.GATI_TELEMETRY !== 'false';
  await initTelemetry(telemetryEnabled);

  // Create MCP server
  const server = new Server(
    {
      name: 'gati-mcp-server',
      version: '1.0.0',
    },
    {
      capabilities: {
        tools: {},
      },
    }
  );

  /**
   * Handler: List available tools
   */
  server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
      tools: allTools.map(tool => {
        const shape = tool.inputSchema.shape as Record<string, any>;
        return {
          name: tool.name,
          description: tool.description,
          inputSchema: {
            type: 'object' as const,
            properties: shape,
            required: Object.keys(shape).filter(
              key => !shape[key].isOptional?.()
            ),
          },
        };
      }),
    };
  });

  /**
   * Handler: Call a tool
   */
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;

    console.error(`[GATI MCP] Tool called: ${name}`);

    // Track telemetry
    await trackQuery();

    // Find the tool
    const tool = allTools.find(t => t.name === name);

    if (!tool) {
      throw new Error(`Unknown tool: ${name}`);
    }

    try {
      // Validate arguments
      const validatedArgs = tool.inputSchema.parse(args || {});

      // Execute tool handler
      const result = await tool.handler(validatedArgs as any);

      return {
        content: [
          {
            type: 'text',
            text: result,
          },
        ],
      };
    } catch (error: any) {
      console.error(`[GATI MCP] Error executing tool ${name}:`, error);

      return {
        content: [
          {
            type: 'text',
            text: `Error: ${error.message || 'An unexpected error occurred'}`,
          },
        ],
        isError: true,
      };
    }
  });

  // Handle shutdown
  process.on('SIGINT', async () => {
    console.error('[GATI MCP] Shutting down...');
    await shutdownTelemetry();
    closeDatabase();
    process.exit(0);
  });

  process.on('SIGTERM', async () => {
    console.error('[GATI MCP] Shutting down...');
    await shutdownTelemetry();
    closeDatabase();
    process.exit(0);
  });

  // Start server with stdio transport
  const transport = new StdioServerTransport();
  await server.connect(transport);

  console.error('[GATI MCP] Server started successfully');
  console.error(`[GATI MCP] Available tools: ${allTools.map(t => t.name).join(', ')}`);
}

// Run the server
main().catch((error) => {
  console.error('[GATI MCP] Fatal error:', error);
  process.exit(1);
});
