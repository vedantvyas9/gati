// Analytics Types for Dashboard

export interface AnalyticsSummaryCards {
  total_installations: number
  active_installations: number
  total_users: number
  total_events: number
  total_agents: number
  total_mcp_queries: number
}

export interface AnalyticsTimeseriesPoint {
  date: string
  daily_active_installations: number
  cumulative_installations: number
  total_events_per_day: number
  active_users: number
  agents_tracked: number
  mcp_queries: number
}

export interface AnalyticsRangeInfo {
  days: number | null
  start_date: string
  end_date: string
}

export interface AnalyticsTimeseriesResponse {
  summary: AnalyticsSummaryCards
  range: AnalyticsRangeInfo
  generated_at: string
  timeseries: AnalyticsTimeseriesPoint[]
  growth_rate_mom?: number | null
  authenticated_count?: number | null
  anonymous_count?: number | null
}

// Engagement Analytics Types
export interface DistributionBucket {
  label: string
  count: number
}

export interface TopInstallation {
  installation_id: string
  user_email: string | null
  lifetime_events: number
  agents_tracked: number
  sdk_version: string | null
  last_active: string | null
}

export interface MCPAdoptionPoint {
  date: string
  adoption_rate: number
}

export interface EngagementAnalyticsResponse {
  average_events_per_installation: number
  events_per_installation_distribution: DistributionBucket[]
  events_today_distribution: DistributionBucket[]
  agents_tracked_distribution: DistributionBucket[]
  average_events_per_agent: number
  mcp_adoption_rate: number
  mcp_adoption_trend: MCPAdoptionPoint[]
  top_installations: TopInstallation[]
  generated_at: string
}

// User Analytics Types
export interface UserSegmentCounts {
  hobbyist: number
  professional: number
  enterprise: number
}

export interface UserStats {
  email: string
  installations: number
  total_agents: number
  total_events: number
  total_mcp_queries: number
  last_active: string | null
  first_seen: string | null
}

export interface UserAnalyticsResponse {
  total_users: number
  segment_counts: UserSegmentCounts
  users: UserStats[]
  total_count: number
  page: number
  page_size: number
  total_pages: number
  top_power_users: UserStats[]
  generated_at: string
}

// Feature Adoption Types
export interface FrameworkStats {
  name: string
  installations_count: number
  total_events: number
}

export interface FrameworkAdoptionPoint {
  date: string
  framework_counts: Record<string, number>
}

export interface VersionDistribution {
  version: string
  count: number
}

export interface VersionAdoptionPoint {
  date: string
  version: string
  installations: number
}

export interface FeatureAdoptionResponse {
  total_mcp_queries: number
  mcp_adoption_rate: number
  mcp_adoption_trend: MCPAdoptionPoint[]
  average_mcp_queries_per_user: number
  mcp_usage_distribution: DistributionBucket[]
  framework_distribution: FrameworkStats[]
  framework_adoption_trend: FrameworkAdoptionPoint[]
  version_distribution: VersionDistribution[]
  version_adoption_timeline: VersionAdoptionPoint[]
  latest_version_adoption_rate: number
  generated_at: string
}

// Retention & Growth Types
export interface RetentionRates {
  week_1: number
  week_4: number
  week_12: number
}

export interface CohortRow {
  signup_week: string
  week_1_retention: number
  week_4_retention: number
  week_12_retention: number
}

export interface ChurnIndicators {
  inactive_7_days: number
  inactive_14_days: number
  inactive_30_days: number
}

export interface GrowthRatePoint {
  period: string
  installation_growth_rate: number
  user_growth_rate: number
}

export interface ConversionRatePoint {
  date: string
  conversion_rate: number
}

export interface NewVsReturningPoint {
  date: string
  new_installations: number
  returning_installations: number
}

export interface RetentionGrowthResponse {
  retention_rates: RetentionRates
  cohort_analysis: CohortRow[]
  churn_indicators: ChurnIndicators
  growth_rates: GrowthRatePoint[]
  conversion_rate_trend: ConversionRatePoint[]
  new_vs_returning: NewVsReturningPoint[]
  generated_at: string
}

// Infrastructure Insights Types
export interface ProjectionData {
  projected_date: string
  projected_events: number
}

export interface HourlyDistribution {
  hour: number
  count: number
}

export interface InfrastructureInsightsResponse {
  daily_event_volume: AnalyticsTimeseriesPoint[]
  peak_events_per_day: number
  average_events_per_installation_per_day: number
  projected_growth: ProjectionData[]
  events_by_hour: HourlyDistribution[]
  generated_at: string
}

