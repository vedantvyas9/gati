-- GATI Database Initialization Script
-- PostgreSQL schema for GATI backend

-- Create agents table
CREATE TABLE IF NOT EXISTS agents (
    name VARCHAR(255) PRIMARY KEY,
    description VARCHAR(1000),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_name ON agents(name);
CREATE INDEX IF NOT EXISTS idx_agent_created_at ON agents(created_at);


-- Create runs table
CREATE TABLE IF NOT EXISTS runs (
    run_id VARCHAR(36) PRIMARY KEY,
    agent_name VARCHAR(255) NOT NULL REFERENCES agents(name) ON DELETE CASCADE,
    environment VARCHAR(50) DEFAULT 'development',
    total_duration_ms FLOAT,
    total_cost FLOAT DEFAULT 0.0,
    tokens_in FLOAT DEFAULT 0,
    tokens_out FLOAT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active',
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_run_id ON runs(run_id);
CREATE INDEX IF NOT EXISTS idx_run_agent_name ON runs(agent_name);
CREATE INDEX IF NOT EXISTS idx_run_created_at ON runs(created_at);
CREATE INDEX IF NOT EXISTS idx_run_agent_created ON runs(agent_name, created_at);
CREATE INDEX IF NOT EXISTS idx_run_status ON runs(status);


-- Create events table
CREATE TABLE IF NOT EXISTS events (
    event_id VARCHAR(36) PRIMARY KEY,
    run_id VARCHAR(36) NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    agent_name VARCHAR(255) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    parent_event_id VARCHAR(36),
    data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_event_id ON events(event_id);
CREATE INDEX IF NOT EXISTS idx_event_run_id ON events(run_id);
CREATE INDEX IF NOT EXISTS idx_event_agent_name ON events(agent_name);
CREATE INDEX IF NOT EXISTS idx_event_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_event_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_event_parent_event_id ON events(parent_event_id);
CREATE INDEX IF NOT EXISTS idx_event_run_timestamp ON events(run_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_event_agent_timestamp ON events(agent_name, timestamp);
CREATE INDEX IF NOT EXISTS idx_event_type_timestamp ON events(event_type, timestamp);

-- Composite index for typical query patterns (agent + time range)
CREATE INDEX IF NOT EXISTS idx_event_agent_time_range ON events(agent_name, timestamp DESC);

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO gati_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO gati_user;
