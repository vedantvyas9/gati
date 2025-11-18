-- ============================================
-- TABLE 1: gati_metrics (Current State)
-- ============================================
CREATE TABLE public.gati_metrics (
  installation_id VARCHAR(255) NOT NULL,
  user_email VARCHAR(255) NULL,
  sdk_version VARCHAR(50) NOT NULL,
  agents_tracked INTEGER NOT NULL,
  events_today INTEGER NOT NULL,
  lifetime_events INTEGER NOT NULL,
  mcp_queries INTEGER NULL DEFAULT 0,
  frameworks_detected TEXT NOT NULL,
  first_seen TIMESTAMP WITHOUT TIME ZONE NULL DEFAULT NOW(),
  last_updated TIMESTAMP WITHOUT TIME ZONE NULL DEFAULT NOW(),
  CONSTRAINT gati_metrics_pkey PRIMARY KEY (installation_id),
  CONSTRAINT fk_user_email FOREIGN KEY (user_email)
    REFERENCES gati_users(email) ON DELETE SET NULL
) TABLESPACE pg_default;

-- Indexes for gati_metrics
CREATE INDEX IF NOT EXISTS idx_metrics_user_email
  ON public.gati_metrics USING btree (user_email) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_metrics_last_updated
  ON public.gati_metrics USING btree (last_updated) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_metrics_first_seen
  ON public.gati_metrics USING btree (first_seen) TABLESPACE pg_default;


-- ============================================
-- TABLE 2: gati_metrics_snapshots (Time Series)
-- ============================================
CREATE TABLE public.gati_metrics_snapshots (
  id SERIAL NOT NULL,
  installation_id VARCHAR(255) NOT NULL,
  user_email VARCHAR(255) NULL,
  sdk_version VARCHAR(50) NOT NULL,
  agents_tracked INTEGER NOT NULL,
  events_today INTEGER NOT NULL,
  lifetime_events INTEGER NOT NULL,
  mcp_queries INTEGER NULL DEFAULT 0,
  frameworks_detected TEXT NOT NULL,
  timestamp TIMESTAMP WITHOUT TIME ZONE NOT NULL,
  recorded_at TIMESTAMP WITHOUT TIME ZONE NULL DEFAULT NOW(),
  CONSTRAINT gati_metrics_snapshots_pkey PRIMARY KEY (id)
) TABLESPACE pg_default;

-- Indexes for gati_metrics_snapshots
CREATE INDEX IF NOT EXISTS idx_snapshots_installation
  ON public.gati_metrics_snapshots USING btree (installation_id) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_snapshots_recorded_at
  ON public.gati_metrics_snapshots USING btree (recorded_at DESC) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_snapshots_user_email
  ON public.gati_metrics_snapshots USING btree (user_email) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_snapshots_time_series
  ON public.gati_metrics_snapshots USING btree (recorded_at DESC, installation_id) TABLESPACE pg_default;


-- ============================================
-- TABLE 3: gati_users (User Accounts)
-- ============================================
CREATE TABLE public.gati_users (
  id SERIAL NOT NULL,
  email VARCHAR(255) NOT NULL,
  api_token VARCHAR(64) NOT NULL,
  created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
  last_active TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
  CONSTRAINT gati_users_pkey PRIMARY KEY (id),
  CONSTRAINT gati_users_api_token_key UNIQUE (api_token),
  CONSTRAINT gati_users_email_key UNIQUE (email)
) TABLESPACE pg_default;

-- Indexes for gati_users
CREATE INDEX IF NOT EXISTS idx_users_api_token
  ON public.gati_users USING btree (api_token) TABLESPACE pg_default;
CREATE INDEX IF NOT EXISTS idx_users_email
  ON public.gati_users USING btree (email) TABLESPACE pg_default;


-- ============================================
-- TABLE 4: gati_verification_codes (Email Verification)
-- ============================================
CREATE TABLE public.gati_verification_codes (
  email VARCHAR(255) NOT NULL,
  code_hash VARCHAR(64) NOT NULL,
  expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
  created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
  attempts INTEGER NULL DEFAULT 0,
  verified BOOLEAN NULL DEFAULT FALSE,
  CONSTRAINT gati_verification_codes_pkey PRIMARY KEY (email)
) TABLESPACE pg_default;

-- Indexes for gati_verification_codes
CREATE INDEX IF NOT EXISTS idx_verification_expires
  ON public.gati_verification_codes USING btree (expires_at) TABLESPACE pg_default;

