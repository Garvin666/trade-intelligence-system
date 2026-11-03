export interface CategoryMap {
  [key: string]: string;
}

export interface HistoryRow {
  date: string;
  category: string;
  market: string;
  search_index: number;
  bestseller_rank: number;
  price_median: number;
  review_growth: number;
  export_value: number;
  competition_index: number;
  sales_volume: number;
}

export interface ForecastRow {
  date: string;
  category: string;
  market: string;
  model: string;
  yhat: number;
  yhat_lower: number;
  yhat_upper: number;
}

export interface Recommendation {
  rank: number;
  category: string;
  market: string;
  score: number;
  six_dimension_score: number;
  verdict: string;
  decision_reason: string;
  dimension_demand: number;
  dimension_trend: number;
  dimension_competition: number;
  dimension_margin: number;
  dimension_compliance: number;
  dimension_evidence: number;
  evidence_missing: boolean;
  forecast_growth: number;
  search_trend: number;
  competition: number;
  review_growth: number;
  reasons: string;
}

export interface GlobePick {
  category: string;
  category_name?: string;
  market: string;
  six_dimension_score: number;
  verdict: string;
  forecast_growth: number;
}

export type GlobePicksMap = Record<string, GlobePick[]>;

export interface MetricItem {
  category: string;
  market: string;
  model: string;
  mape: number;
  mae: number;
}

export interface ModelMetricsPayload {
  baseline?: MetricItem[];
  advanced?: MetricItem[];
  statsforecast?: MetricItem[];
  business_metrics?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface MarketIntelPayload {
  rankings: {
    count: number;
    items: RankingRow[];
    source_level?: string;
    providers?: Record<string, unknown>;
    fallback_used?: boolean;
    date?: string;
    real_count?: number;
    mock_count?: number;
  };
  searchTrends: {
    count: number;
    items: Record<string, unknown>[];
    coverage?: { requested?: number; real?: number; mock?: number };
    provider?: string;
    fallback_used?: boolean;
    date?: string;
  };
  exportValue: {
    count: number;
    items: ExportValueRow[];
    provider?: string;
    period?: string;
    fallback_used?: boolean;
  };
  risk: { count: number; items: RiskRow[] };
  cost: { count: number; items: CostRow[] };
  compare: { count: number; items: CompareRow[] };
  reviews: { count: number; items: ReviewRow[] };
  competition: { count: number; items: CompetitionRow[] };
  status?: {
    online?: Record<string, unknown>;
    trends?: Record<string, unknown>;
    platform_rankings?: Record<string, unknown>;
    customs?: Record<string, unknown>;
    suppliers?: Record<string, unknown>;
    policy?: Record<string, unknown>;
    as_of_label?: string;
  };
}

export interface TradeReportPayload {
  generated_at?: string;
  [key: string]: unknown;
}

export interface PolicyEvent {
  code: string;
  title: string;
  market: string;
  region: string;
  policy_type: string;
  effective_date: string;
  published_at: string;
  description: string;
  source: string;
  url: string;
  impact_level: string;
  direction: string;
  actions: string[];
  rate_ad_valorem: number;
  min_duty_usd: number;
  cost_adjustment_pct: number;
  verified: boolean;
  provider: string;
  source_type: string;
}

export interface PolicyImpactRow {
  category: string;
  category_name: string;
  market: string;
  market_name?: string;
  unit_price_usd: number;
  tariff_before: number;
  tariff_after: number;
  duty_before: number;
  duty_after: number;
  cost_increase_before: number;
  cost_increase_after: number;
  margin_before: number;
  margin_after: number;
  margin_delta_pct: number;
  risk_before: string;
  risk_after: string;
  verdict_before: string;
  verdict_after: string;
  affected: boolean;
}

export interface PolicyImpactPayload {
  event_code: string;
  event_title: string;
  event_description?: string;
  market: string;
  market_name?: string;
  effective_date: string;
  source?: string;
  url?: string;
  policy_type?: string;
  source_type?: string;
  provider?: string;
  verified?: boolean;
  published_at?: string;
  actions?: string[];
  rate_ad_valorem?: number;
  min_duty_usd?: number;
  trends_status?: {
    available: boolean;
    generated_at?: string;
    provider?: string;
    fallback_used?: boolean;
    note?: string;
  };
  before_date?: string;
  after_date?: string;
  total_categories: number;
  affected_count: number;
  worst?: PolicyImpactRow | null;
  rows: PolicyImpactRow[];
}

export interface EvidenceLedgerItem {
  key?: string;
  title?: string;
  source?: string;
  fetched_at?: string | null;
  effective_date?: string | null;
  expires_at?: string | null;
  validity_days?: number | null;
  hs_version?: string | null;
  formula?: string | null;
  model_version?: string | null;
  confidence_interval?: unknown;
  review_status?: string;
  url?: string | null;
  status?: string;
  expiry_status?: {
    status?: string;
    days_left?: number | null;
    message?: string;
  };
  [key: string]: unknown;
}

export interface EvidenceLedgerPayload {
  schema_version: number;
  count: number;
  expired_count: number;
  items: EvidenceLedgerItem[];
}

export interface SellerMagicImportSummary {
  rows: number;
  matched_columns: number;
  unmatched_columns: string[];
  numeric_columns: string[];
  dropped_rows: number;
  keyword_count: number;
  avg_price?: number | null;
}

export interface SellerMagicImportResult {
  ok: boolean;
  mapping: {
    matched?: Record<string, string>;
    unmatched?: string[];
    missing?: string[];
    dropped?: number;
    numeric_columns?: string[];
  };
  summary: SellerMagicImportSummary;
  top_keywords?: Array<{
    keyword?: string;
    avg_price?: number | null;
  }>;
  file: string;
}

export interface VerdictExportResult {
  ok: boolean;
  csv: string;
  row_count: number;
  webhook?: {
    status: string;
    http?: number;
    detail?: string;
  } | null;
}

export interface DashboardData {
  categories: CategoryMap;
  markets: CategoryMap;
  models: CategoryMap;
  models_order: string[];
  fx_rate?: number;
  history: HistoryRow[];
  forecast: ForecastRow[];
  recommendations: Recommendation[];
  metrics: {
    baseline: MetricItem[];
    advanced: MetricItem[];
    statsforecast?: MetricItem[];
  };
  trade: Record<string, unknown>;
  policy_events: PolicyEvent[];
  policy_candidates: PolicyEvent[];
  policy_snapshot: Record<string, unknown>;
  analysis: Record<string, unknown>;
  crawler: Record<string, unknown>;
  data_status: DataStatus;
}

export interface DataStatus {
  generated_at: string;
  data_as_of: string;
  as_of_label?: string;
  next_update?: string;
  online?: Record<string, unknown>;
  crawler?: Record<string, unknown>;
  trends?: Record<string, unknown>;
  policy?: Record<string, unknown>;
  platform_rankings?: Record<string, unknown>;
  market_daily?: Record<string, unknown>;
  customs?: Record<string, unknown>;
  suppliers?: Record<string, unknown>;
  crawl_quality?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface TradeDecision extends Record<string, unknown> {
  category: string;
  market: string;
  risk_level: string;
  margin_pct: number;
  effective_tariff_rate: number;
  feasibility_score: number;
  hs_code: string;
  hs_description: string;
}

export interface JobSummary {
  name: string;
  label: string;
  status: "idle" | "running" | "done" | "error" | "cancelled";
  exclusive?: boolean;
  job_id?: string | null;
  progress?: { stage?: string; message?: string } | null;
  error?: string | null;
  result?: unknown;
  started_at?: string | null;
  finished_at?: string | null;
  updated_at?: string;
  date?: string;
  verified_count?: number;
  [key: string]: unknown;
}

export interface JobSummaryList {
  count: number;
  items: JobSummary[];
}

export interface HealthStatus {
  status: string;
  service?: string;
  mcp?: boolean;
  jobs?: JobSummaryList;
  data_status?: DataStatus;
  data_files?: Record<string, boolean>;
  [key: string]: unknown;
}

export interface EngineeringStatus {
  data_as_of?: string;
  generated_at?: string;
  provider?: string;
  fallback_used?: boolean;
  snapshot_sources?: number;
  capabilities?: Record<string, unknown>;
  test_count?: number;
  test_passed?: number;
  build?: Record<string, unknown>;
  endpoints?: string[];
  [key: string]: unknown;
}

export interface SystemEval {
  source: string;
  system_eval: Record<string, unknown>;
  model_summary?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface AiConfigPayload {
  api_key?: string;
  base_url?: string;
  model?: string;
  preset?: string;
  timeout?: number;
  search_provider?: string;
  search_api_key?: string;
  search_api_url?: string;
  search_max_results?: number;
}

export interface AiConfigStatus extends AiConfigPayload {
  configured: boolean;
  has_key: boolean;
  search_has_key?: boolean;
  source?: string;
  [key: string]: unknown;
}

export interface LaunchReportResult {
  report: string;
  mode?: string;
  generated_at?: string;
  ai?: {
    enabled?: boolean;
    used?: boolean;
    configured?: boolean;
    provider?: Record<string, unknown>;
  };
}

export type LaunchReportStreamPhase = "connecting" | "streaming" | "done";

export interface LaunchReportStreamStatus {
  phase: LaunchReportStreamPhase;
  elapsed_ms?: number;
  chars?: number;
}

export interface TestResult {
  ok?: boolean;
  error?: string;
  latency_ms?: number;
  provider?: string;
  [key: string]: unknown;
}

export interface FeedbackItem {
  id?: number | string;
  created_at?: string;
  content?: string;
  rating?: number;
  category?: string;
  [key: string]: unknown;
}

export interface FeedbackList {
  count: number;
  items: FeedbackItem[];
}

export type ScoringWeights = Record<string, number>;

export interface ControlMetrics {
  source: string;
  status: string;
  generated_at?: string;
  train_dates?: string;
  holdout_dates?: string;
  total_cells?: number;
  scope?: string;
  models?: Record<string, unknown>;
  system_baseline?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface ControlRunStatus {
  status: "idle" | "running" | "done" | "error";
  job_id?: string;
  mode?: string;
  progress?: Record<string, unknown> | null;
  error?: string | null;
  started_at?: string;
  finished_at?: string;
  [key: string]: unknown;
}

export interface RankingRow {
  rank?: number;
  category?: string;
  category_name?: string;
  market?: string;
  market_name?: string;
  platform?: string;
  title?: string;
  price?: number;
  score?: number;
  [key: string]: unknown;
}

export interface RiskRow {
  category?: string;
  category_name?: string;
  market?: string;
  market_name?: string;
  risk_score?: number;
  risk_level?: string;
  risk_reason?: string;
  [key: string]: unknown;
}

export interface CostRow {
  category?: string;
  category_name?: string;
  market?: string;
  market_name?: string;
  gross_margin?: number;
  logistics_cost?: number;
  return_rate?: number;
  ad_cost_index?: number;
  compliance_risk?: number;
  risk_score?: number;
  [key: string]: unknown;
}

export interface CompareRow {
  market?: string;
  market_name?: string;
  avg_sales_volume?: number;
  avg_competition_index?: number;
  avg_price_median?: number;
  avg_export_value?: number;
  [key: string]: unknown;
}

export interface ReviewRow {
  category?: string;
  category_name?: string;
  market?: string;
  market_name?: string;
  review_growth?: number;
  review_volume?: number;
  [key: string]: unknown;
}

export interface ExportValueRow {
  category?: string;
  category_name?: string;
  market?: string;
  market_name?: string;
  export_value?: number;
  [key: string]: unknown;
}

export interface CompetitionRow {
  category?: string;
  category_name?: string;
  market?: string;
  market_name?: string;
  competition_index?: number;
  [key: string]: unknown;
}

export interface SearchResultItem {
  title?: string;
  snippet?: string;
  link?: string;
  query?: string;
  [key: string]: unknown;
}

export interface SearchResult {
  provider?: string;
  fallback_used?: boolean;
  results?: SearchResultItem[];
  error?: string;
  [key: string]: unknown;
}

export interface ResearchResult {
    sources?: SearchResultItem[];
    summary?: string;
    provider?: string;
    fallback_used?: boolean;
    mock_count?: number;
    mock_used?: boolean;
    [key: string]: unknown;
  }

export interface CrawlerStatusDetail {
  status?: string;
  combos?: number;
  real_combos?: number;
  mock_combos?: number;
  provider?: string;
  [key: string]: unknown;
}

export interface CrawlerSignals {
  status?: string | CrawlerStatusDetail;
  count?: number;
  combos?: unknown[];
  [key: string]: unknown;
}

export interface EdaReport {
  title?: string;
  summary?: string;
  anomalies?: unknown[];
  ab_test?: unknown;
  report_url?: string;
  [key: string]: unknown;
}

export interface HsCode {
  hs_code?: string;
  hs_description?: string;
  hs_verified?: boolean;
  category?: string;
  market?: string;
  [key: string]: unknown;
}

export interface CatalogOption {
  key: string;
  label?: string;
  [key: string]: unknown;
}

export interface CatalogPayload {
  fx_rate?: number;
  data?: {
    categories?: CatalogOption[];
    markets?: CatalogOption[];
    platforms?: CatalogOption[];
    recommendations?: unknown[];
    signals?: string[];
  };
  [key: string]: unknown;
}

export interface SuppliersPayload {
  status?: string;
  rows?: unknown[];
  coverage?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface PolicyRefreshResult {
  updated_at?: string;
  verified_count?: number;
  [key: string]: unknown;
}

export type EnvCheckStatus = "ok" | "warn" | "fail" | "skip";

export interface EnvCheckItem {
  id: string;
  label: string;
  status: EnvCheckStatus;
  detail: string;
  duration_ms: number;
}

export interface EnvCheckGroup {
  label: string;
  results: EnvCheckItem[];
}

export interface EnvCheckReport {
  generated_at?: string;
  python?: string;
  depth?: string;
  base_url?: string;
  groups?: Record<string, EnvCheckGroup>;
  summary?: { ok: number; warn: number; fail: number; skip: number };
  overall?: "ok" | "fail";
  [key: string]: unknown;
}

export interface ExamplePreset {
  id: string;
  label: string;
  [key: string]: unknown;
}

export interface ExamplesPayload {
  dashboard?: ExamplePreset[];
  four_brain?: ExamplePreset[];
  trade?: ExamplePreset[];
  launch_report?: ExamplePreset[];
  workflow?: ExamplePreset[];
  [key: string]: unknown;
}

export interface AnomalyRow {
  category?: string;
  market?: string;
  column?: string;
  date?: string;
  value?: number;
  score?: number;
  method?: string;
  [key: string]: unknown;
}

export interface AnomalyPayload {
  enabled?: boolean;
  generated_at?: string;
  date?: string;
  fallback_used?: boolean;
  source_count?: number;
  method?: string;
  rows: AnomalyRow[];
  [key: string]: unknown;
}

export interface HsCodeRow {
  category: string;
  hs_code: string;
  description?: string;
  market?: string;
  base_tariff_rate?: number;
  verified?: boolean;
  note?: string;
  [key: string]: unknown;
}

export interface FourBrainBatchItem {
  ok: boolean;
  label: string;
  result?: Record<string, unknown>;
  error?: string;
  [key: string]: unknown;
}

export interface FourBrainBatchResult {
  items: FourBrainBatchItem[];
  summary: {
    total: number;
    ok: number;
    error: number;
    use_ai: boolean;
  };
  [key: string]: unknown;
}

export interface SelectionDraft {
  id?: string;
  label?: string;
  keyword?: string;
  category?: string;
  market?: string;
  price?: number;
  price_min?: number;
  price_max?: number;
  budget?: number;
  target_margin?: number;
  unit_cost?: number;
  procurement_cost_cny?: number;
  verdict?: string;
  score?: number;
  fourBrainResult?: Record<string, unknown>;
  isDemo?: boolean;
  [key: string]: unknown;
}

export interface WatchlistItem {
  id: string;
  label: string;
  category: string;
  market: string;
  keyword?: string;
  verdict?: string;
  score?: number;
  createdAt: string;
  isDemo?: boolean;
  [key: string]: unknown;
}

export interface TradeScenario {
  id: string;
  label: string;
  category: string;
  market: string;
  unit_price_usd: number;
  procurement_cost_cny: number;
  quantity: number;
  ad_rate: number;
  return_rate: number;
  inventory_days: number;
  fx_rate: number;
  result?: TradeDecision;
  createdAt: string;
  isDemo?: boolean;
  [key: string]: unknown;
}

export interface BatchRunItem {
  label: string;
  ok?: boolean;
  error?: string;
  verdict?: string;
  score?: number;
  result?: Record<string, unknown>;
}

export interface BatchRun {
  id: string;
  label: string;
  createdAt: string;
  items: BatchRunItem[];
  isDemo?: boolean;
}
