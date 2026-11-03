import type {
  AiConfigPayload,
  AiConfigStatus,
  AnomalyPayload,
  CatalogPayload,
  CompetitionRow,
  ControlMetrics,
  ControlRunStatus,
  CostRow,
  CrawlerSignals,
  DashboardData,
  DataStatus,
  EdaReport,
  EngineeringStatus,
  EnvCheckReport,
  EvidenceLedgerPayload,
  ExamplesPayload,
  ExportValueRow,
  FeedbackItem,
  FeedbackList,
  FourBrainBatchResult,
  GlobePicksMap,
  HealthStatus,
  HsCode,
  HsCodeRow,
  JobSummary,
  JobSummaryList,
  LaunchReportResult,
  LaunchReportStreamStatus,
  MarketIntelPayload,
  ModelMetricsPayload,
  PolicyImpactPayload,
  PolicyRefreshResult,
  RankingRow,
  ResearchResult,
  ReviewRow,
  RiskRow,
  ScoringWeights,
  SearchResult,
  SellerMagicImportResult,
  SuppliersPayload,
  SystemEval,
  TestResult,
  TradeDecision,
  TradeReportPayload,
  VerdictExportResult,
} from "./types";
import { IS_OFFLINE } from "./offline";
import {
  OFFLINE_FOUR_BRAIN_EXAMPLES,
  OFFLINE_LAUNCH_EXAMPLES,
} from "./fourBrainExamples";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

/**
 * 离线回退汇率（USD→CNY）。必须与后端 `src/trade/cost.py` 的 DEFAULT_FX_RATE 保持一致；
 * 在线与离线快照数据（/api/dashboard-data 与 /api/catalog 的 fx_rate 字段）优先使用，
 * 仅在快照缺失时回退到本常量，避免口径漂移。
 */
const DEFAULT_FX_RATE = 7.15;
let fallbackRecommendationRowsPromise: Promise<Record<string, unknown>[]> | null =
  null;

function offlineFxRate(): number {
  const snapshot = window.__TRADE_INTEL_OFFLINE__ as Partial<DashboardData> | undefined;
  const rate = snapshot?.fx_rate;
  return typeof rate === "number" && Number.isFinite(rate) && rate > 0 ? rate : DEFAULT_FX_RATE;
}

const OFFLINE_EXAMPLES: ExamplesPayload = {
  dashboard: [
    {
      id: "dashboard_latiao_us",
      label: "辣条 × 美国",
      category: "cn_latiao",
      market: "us",
      keyword: "latiao spicy strips",
    },
    {
      id: "dashboard_longjing_uk",
      label: "西湖龙井 × 英国",
      category: "cn_longjing",
      market: "uk",
      keyword: "longjing green tea",
    },
    {
      id: "dashboard_dumplings_jp",
      label: "速冻水饺 × 日本",
      category: "cn_frozen_dumplings",
      market: "jp",
      keyword: "frozen chinese dumplings",
    },
    {
      id: "dashboard_laoganma_ca",
      label: "老干妈辣椒酱 × 加拿大",
      category: "cn_laoganma",
      market: "ca",
      keyword: "laoganma chili crisp",
    },
    {
      id: "dashboard_beef_jerky_au",
      label: "麻辣牛肉干 × 澳大利亚",
      category: "cn_beef_jerky",
      market: "au",
      keyword: "sichuan spicy beef jerky",
    },
    {
      id: "dashboard_changsha_mifen_sea",
      label: "长沙米粉 × 东南亚",
      category: "cn_changsha_mifen",
      market: "sea",
      keyword: "changsha rice noodles",
    },
    {
      id: "dashboard_hotpot_kr",
      label: "自热火锅 × 韩国",
      category: "cn_self_heating_hotpot",
      market: "kr",
      keyword: "self heating hot pot",
    },
    {
      id: "dashboard_tanghulu_de",
      label: "糖葫芦 × 德国",
      category: "cn_tanghulu",
      market: "de",
      keyword: "tanghulu candied hawthorn",
    },
    {
      id: "dashboard_goji_fr",
      label: "宁夏枸杞 × 法国",
      category: "cn_ningxia_goji",
      market: "fr",
      keyword: "ningxia goji berries",
    },
    {
      id: "dashboard_mooncake_vn",
      label: "广式月饼 × 越南",
      category: "cn_mooncake",
      market: "vn",
      keyword: "cantonese mooncake",
    },
    {
      id: "dashboard_baijiu_ru",
      label: "小瓶白酒 × 俄罗斯",
      category: "cn_baijiu_mini",
      market: "ru",
      keyword: "baijiu mini bottle",
    },
    {
      id: "dashboard_goji_honey_ae",
      label: "枸杞蜂蜜 × 阿联酋",
      category: "cn_goji_honey",
      market: "ae",
      keyword: "goji honey",
    },
  ],
  four_brain: OFFLINE_FOUR_BRAIN_EXAMPLES,
  trade: [
    {
      id: "trade_latiao_us",
      label: "辣条 × 美国",
      inputs: {
        category: "cn_latiao",
        market: "us",
        product_name: "辣条（网红休闲零食）",
        unit_price_usd: 4.9,
        procurement_cost_cny: 12,
      },
    },
  ],
  launch_report: OFFLINE_LAUNCH_EXAMPLES,
  workflow: [
    {
      id: "workflow_latiao_us",
      label: "辣条出口完整流程",
      plan: {
        keyword: "辣条（网红休闲零食）",
        category: "cn_latiao",
        market: "us",
        price: 4.9,
        procurement_cost_cny: 12,
      },
    },
  ],
};

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`API ${response.status}: ${path}`);
  }
  return (await response.json()) as T;
}

export async function apiPost<T>(path: string, payload: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `API ${response.status}: ${path}`);
  }
  return (await response.json()) as T;
}

export async function apiUpload<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `API ${response.status}: ${path}`);
  }
  return (await response.json()) as T;
}

export async function apiPostBlob(path: string, payload: unknown): Promise<Blob> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `API ${response.status}: ${path}`);
  }
  return response.blob();
}

export async function apiGetBlob(path: string): Promise<Blob> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`API ${response.status}: ${path}`);
  }
  return response.blob();
}

export async function getDataStatus(): Promise<DataStatus> {
  if (IS_OFFLINE) {
    return window.__TRADE_INTEL_OFFLINE__?.data_status ?? ({} as DataStatus);
  }
  return apiGet<DataStatus>("/api/data/status");
}

export async function fetchExamples(): Promise<ExamplesPayload> {
  if (IS_OFFLINE) return OFFLINE_EXAMPLES;
  return apiGet<ExamplesPayload>("/api/examples");
}

export async function fetchAnomalies(): Promise<AnomalyPayload> {
  if (IS_OFFLINE) return { rows: [] };
  return apiGet<AnomalyPayload>("/api/anomalies");
}

export async function fetchHsCodes(
  params: { q?: string; category?: string; market?: string } = {},
): Promise<{ count: number; items: HsCodeRow[] }> {
  const query = new URLSearchParams();
  if (params.q) query.set("q", params.q);
  if (params.category) query.set("category", params.category);
  if (params.market) query.set("market", params.market);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiGet<{ count: number; items: HsCodeRow[] }>(`/api/trade/hs-codes${suffix}`);
}

export async function postFourBrainBatch(payload: {
  items: Record<string, unknown>[];
  ai?: boolean;
}): Promise<FourBrainBatchResult> {
  if (IS_OFFLINE) {
    return buildOfflineFourBrainBatch(payload.items);
  }
  return apiPost<FourBrainBatchResult>("/api/four-brain/batch", payload);
}

export interface DashboardQuery {
  category?: string;
  market?: string;
  model?: string;
}

export async function fetchDashboardData(query: DashboardQuery): Promise<DashboardData> {
  if (IS_OFFLINE) {
    return window.__TRADE_INTEL_OFFLINE__ ?? ({} as DashboardData);
  }
  const params = new URLSearchParams();
  if (query.category) params.set("category", query.category);
  if (query.market) params.set("market", query.market);
  if (query.model) params.set("model", query.model);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return apiGet<DashboardData>(`/api/dashboard-data${suffix}`);
}

export async function fetchTradeDecision(params: {
  category: string;
  market: string;
  unit_price_usd: number;
  procurement_cost_cny: number;
  product_name?: string;
}): Promise<TradeDecision> {
  if (IS_OFFLINE) {
    return buildOfflineTradeDecision(params, offlineFxRate());
  }
  const query = new URLSearchParams({
    category: params.category,
    market: params.market,
    unit_price_usd: String(params.unit_price_usd),
    procurement_cost_cny: String(params.procurement_cost_cny),
  });
  if (params.product_name) query.set("product_name", params.product_name);
  return apiGet<TradeDecision>(`/api/trade/decision?${query.toString()}`);
}

export async function fetchFourBrain(payload: Record<string, unknown>) {
  if (IS_OFFLINE) {
    return buildOfflineFourBrain(payload);
  }
  return apiPost<Record<string, unknown>>("/api/four-brain", payload);
}

export async function generateTemplateReport(payload: { prompt: string }) {
  return apiPost<LaunchReportResult>("/api/four-brain/launch-report", payload);
}

interface LaunchReportSseEvent {
  event: string;
  data?: Record<string, unknown>;
}

function parseLaunchReportSseBlock(raw: string): LaunchReportSseEvent | null {
  let event = "";
  let dataText = "";
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) dataText += line.slice(5).trim();
  }
  if (!dataText) return null;
  try {
    return { event, data: JSON.parse(dataText) as Record<string, unknown> };
  } catch {
    return null;
  }
}

export interface LaunchReportStreamHandlers {
  onStatus?: (status: LaunchReportStreamStatus) => void;
  onDelta?: (content: string) => void;
}

export async function streamLaunchReport(
  payload: { prompt: string },
  handlers: LaunchReportStreamHandlers = {},
  signal?: AbortSignal,
): Promise<LaunchReportResult> {
  const response = await fetch(`${API_BASE}/api/four-brain/launch-report/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(
      detail || `API ${response.status}: /api/four-brain/launch-report/stream`,
    );
  }
  if (!response.body) {
    throw new Error("浏览器不支持流式响应");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let report = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let index: number;
    while ((index = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, index);
      buffer = buffer.slice(index + 2);
      const parsed = parseLaunchReportSseBlock(raw);
      if (!parsed) continue;
      if (parsed.event === "status" && handlers.onStatus) {
        const data = (parsed.data ?? {}) as Partial<LaunchReportStreamStatus>;
        handlers.onStatus({
          phase:
            data.phase === "streaming" || data.phase === "done"
              ? data.phase
              : "connecting",
          elapsed_ms:
            typeof data.elapsed_ms === "number" ? data.elapsed_ms : undefined,
          chars: typeof data.chars === "number" ? data.chars : undefined,
        });
      } else if (parsed.event === "delta") {
        const content = String(parsed.data?.content ?? "");
        if (content) {
          report += content;
          handlers.onDelta?.(content);
        }
      } else if (parsed.event === "error") {
        throw new Error(String(parsed.data?.message ?? "报告生成失败"));
      } else if (parsed.event === "done") {
        const doneData = (parsed.data ?? {}) as Partial<LaunchReportResult>;
        if (doneData.report) report = String(doneData.report);
        return {
          report,
          mode: doneData.mode,
          generated_at: doneData.generated_at,
          ai: doneData.ai,
        };
      }
    }
  }
  return { report };
}

export function fetchHealth() {
  return apiGet<HealthStatus>("/api/health");
}

export function fetchEngineeringStatus() {
  return apiGet<EngineeringStatus>("/api/engineering/status");
}

export function fetchEnvCheck(groups?: string, depth = "quick") {
  const params = new URLSearchParams({ depth });
  if (groups) params.set("groups", groups);
  return apiGet<EnvCheckReport>(`/api/check?${params.toString()}`);
}

export function fetchSystemEval() {
  return apiGet<SystemEval>("/api/system/eval");
}

export function fetchSuppliers() {
  return apiGet<SuppliersPayload>("/api/data/suppliers");
}

export function fetchJobs() {
  return apiGet<JobSummaryList>("/api/jobs");
}

export function fetchJobStatus(name: string) {
  return apiGet<JobSummary>(`/api/jobs/${encodeURIComponent(name)}`);
}

export function startJob(name: string, payload: Record<string, unknown> = {}) {
  return apiPost<{ ok: boolean; job: JobSummary }>(
    `/api/jobs/${encodeURIComponent(name)}/start`,
    payload,
  );
}

export function stopJob(name: string) {
  return apiPost<{ name: string; accepted: boolean; status: string }>(
    `/api/jobs/${encodeURIComponent(name)}/stop`,
    {},
  );
}

export function fetchAiConfig() {
  return apiGet<AiConfigStatus>("/api/ai/config");
}

export function saveAiConfig(payload: AiConfigPayload) {
  return apiPost<AiConfigStatus>("/api/ai/config", payload);
}

export function testAiConnection(payload: Record<string, unknown> = {}) {
  return apiPost<TestResult>("/api/ai/test", payload);
}

export function testSearchConnection(payload: Record<string, unknown> = {}) {
  return apiPost<TestResult>("/api/search/test", payload);
}

export function fetchControlMetrics() {
  return apiGet<ControlMetrics>("/api/control/metrics");
}

export function startControlRun(payload: Record<string, unknown>) {
  return apiPost<ControlRunStatus>("/api/control/run", payload);
}

export function fetchControlRunStatus() {
  return apiGet<ControlRunStatus>("/api/control/run/status");
}

export function fetchControlWebSetup() {
  return apiGet<Record<string, unknown>>("/api/control/web/setup");
}

export function saveControlWebResponse(payload: Record<string, unknown>) {
  return apiPost<Record<string, unknown>>("/api/control/web/save", payload);
}

export function downloadControlTrainData() {
  return apiGetBlob("/api/control/train-data");
}

export function fetchFeedbackList() {
  return apiGet<FeedbackList>("/api/feedback");
}

export function postFeedback(payload: Record<string, unknown>) {
  return apiPost<{ ok: boolean; feedback: FeedbackItem }>("/api/feedback", payload);
}

export function fetchScoringWeights() {
  return apiGet<ScoringWeights>("/api/scoring/weights");
}

export function saveScoringWeights(payload: ScoringWeights) {
  return apiPost<{ ok: boolean; weights: ScoringWeights }>("/api/scoring/weights", payload);
}

export function fetchHistory(filters: DashboardQuery = {}) {
  return apiGet<{ count: number; items: Record<string, unknown>[] }>(
    `/api/history${querySuffix(filters)}`,
  );
}

export function fetchForecast(filters: DashboardQuery = {}) {
  return apiGet<{ count: number; items: Record<string, unknown>[] }>(
    `/api/forecast${querySuffix(filters)}`,
  );
}

export function fetchModelMetrics(filters: DashboardQuery = {}) {
  return apiGet<ModelMetricsPayload>(`/api/model-metrics${querySuffix(filters)}`);
}

export function fetchMarketIntel(filters: DashboardQuery = {}) {
  return apiGet<MarketIntelPayload>(`/api/market-intel${querySuffix(filters)}`);
}

/** 离线快照推荐过滤：市场/品类过滤 + No-Go 放行逻辑（可单测的纯函数）。 */
export function filterRecommendationsOffline(
  rows: Record<string, unknown>[],
  filters: DashboardQuery & { include_no_go?: boolean; top?: number } = {},
): Record<string, unknown>[] {
  return rows
    .filter(
      (row) =>
        (!filters.category || row.category === filters.category) &&
        (!filters.market || row.market === filters.market) &&
        // include_no_go=true 时放行 No-Go 行（供空态取判定原因）；
        // 否则（默认）排除 No-Go，只留 Go/Conditional
        (filters.include_no_go || row.verdict !== "No-Go"),
    )
    .sort(
      (a, b) =>
        Number(b.six_dimension_score ?? 0) - Number(a.six_dimension_score ?? 0),
    )
    .slice(0, filters.top ?? 100);
}

export function fetchRecommendations(
  filters: DashboardQuery & { include_no_go?: boolean; top?: number } = {},
) {
  if (IS_OFFLINE) {
    const snapshot = window.__TRADE_INTEL_OFFLINE__ as
      | Partial<DashboardData>
      | undefined;
    const rows = (snapshot?.recommendations ?? []) as unknown as Record<
      string,
      unknown
    >[];
    const filtered = filterRecommendationsOffline(rows, filters);
    return Promise.resolve({ count: filtered.length, items: filtered });
  }
  const params = new URLSearchParams();
  if (filters.category) params.set("category", filters.category);
  if (filters.market) params.set("market", filters.market);
  if (filters.model) params.set("model", filters.model);
  if (filters.include_no_go) params.set("include_no_go", "true");
  if (filters.top) params.set("top", String(filters.top));
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return apiGet<{ count: number; items: Record<string, unknown>[] }>(
    `/api/recommendations${suffix}`,
  );
}

/** 首页地球悬停数据：按市场并行取 Top 4 推荐，离线时从内置快照过滤。 */
export async function fetchGlobeMarketPicks(
  marketIds: string[],
): Promise<GlobePicksMap> {
  if (IS_OFFLINE) {
    const snapshot = window.__TRADE_INTEL_OFFLINE__ as
      | Partial<DashboardData>
      | undefined;
    const rows = (snapshot?.recommendations ?? []) as unknown as Record<
      string,
      unknown
    >[];
    return buildGlobePicksFromRows(marketIds, rows);
  }

  const entries = await Promise.all(
    marketIds.map(async (market) => {
      try {
        const response = await fetchRecommendations({ market, top: 4 });
        let picks = response.items.slice(0, 4);
        if (picks.length < 4) {
          const allRows = (
            await fetchRecommendations({
              market,
              top: 4,
              include_no_go: true,
            })
          ).items;
          picks = fillGlobePicks(picks, allRows);
        }
        return [market, normalizeGlobePicks(picks)];
      } catch {
        const fallbackRows = await loadFallbackRecommendationRows();
        return [
          market,
          buildGlobePicksFromRows([market], fallbackRows)[market] ?? [],
        ];
      }
    }),
  );
  return Object.fromEntries(entries);
}

async function loadFallbackRecommendationRows(): Promise<
  Record<string, unknown>[]
> {
  if (!fallbackRecommendationRowsPromise) {
    fallbackRecommendationRowsPromise = fetch(
      `${API_BASE}/output/dashboard-data.json`,
    )
      .then(async (response) => {
        if (!response.ok) return [] as Record<string, unknown>[];
        const payload = (await response.json()) as {
          recommendations?: Record<string, unknown>[];
        };
        return payload.recommendations ?? [];
      })
      .catch(() => []);
  }
  return fallbackRecommendationRowsPromise;
}

/** 离线快照分组：供单元测试与离线分支共用。 */
export function buildGlobePicksFromRows(
  marketIds: string[],
  rows: Record<string, unknown>[],
): GlobePicksMap {
  return Object.fromEntries(
    marketIds.map((market) => {
      const preferred = filterRecommendationsOffline(rows, {
        market,
        top: 4,
      });
      const allRows = rows
        .filter((row) => row.market === market)
        .sort(
          (left, right) =>
            Number(right.six_dimension_score ?? 0) -
            Number(left.six_dimension_score ?? 0),
        );
      return [market, normalizeGlobePicks(fillGlobePicks(preferred, allRows))];
    }),
  );
}

function fillGlobePicks(
  preferred: Record<string, unknown>[],
  allRows: Record<string, unknown>[],
): Record<string, unknown>[] {
  const picked = preferred.slice(0, 4);
  const pickedKeys = new Set(picked.map((row) => String(row.category ?? "")));

  for (const row of allRows) {
    if (picked.length >= 4) break;
    const key = String(row.category ?? "");
    if (pickedKeys.has(key)) continue;
    picked.push(row);
    pickedKeys.add(key);
  }

  return picked;
}

function normalizeGlobePicks(
  rows: Record<string, unknown>[],
): GlobePicksMap[string] {
  return rows.map((row) => ({
    category: String(row.category ?? ""),
    category_name:
      typeof row.category_name === "string" ? row.category_name : undefined,
    market: String(row.market ?? ""),
    six_dimension_score: Number(row.six_dimension_score ?? 0),
    verdict: String(row.verdict ?? ""),
    forecast_growth: Number(row.forecast_growth ?? 0),
  }));
}

export function fetchSearchTrends(filters: DashboardQuery = {}) {
  return apiGet<{ count: number; items: Record<string, unknown>[] }>(
    `/api/search/trends${querySuffix(filters)}`,
  );
}

export function fetchReviewsSummary(filters: DashboardQuery = {}) {
  return apiGet<{ count: number; items: ReviewRow[] }>(
    `/api/reviews/summary${querySuffix(filters)}`,
  );
}

export function fetchExportValue(filters: DashboardQuery = {}) {
  return apiGet<{ count: number; items: ExportValueRow[] }>(
    `/api/trade/export-value${querySuffix(filters)}`,
  );
}

export function fetchCompetitionIndex(filters: DashboardQuery = {}) {
  return apiGet<{ count: number; items: CompetitionRow[] }>(
    `/api/competition/index${querySuffix(filters)}`,
  );
}

export function fetchPlatformRankings(filters: DashboardQuery & { platform?: string } = {}) {
  const params = new URLSearchParams();
  if (filters.category) params.set("category", filters.category);
  if (filters.market) params.set("market", filters.market);
  if (filters.platform) params.set("platform", filters.platform);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return apiGet<{ count: number; items: RankingRow[] }>(
    `/api/platform/rankings${suffix}`,
  );
}

export function fetchRiskOverview(filters: DashboardQuery = {}) {
  return apiGet<{ count: number; items: RiskRow[] }>(
    `/api/risk/overview${querySuffix(filters)}`,
  );
}

export function fetchCostMetrics(filters: DashboardQuery = {}) {
  return apiGet<{ count: number; items: CostRow[] }>(
    `/api/cost/metrics${querySuffix(filters)}`,
  );
}

export function fetchMarketCompare(filters: DashboardQuery = {}) {
  return apiGet<{ count: number; items: Record<string, unknown>[] }>(
    `/api/market/compare${querySuffix(filters)}`,
  );
}

export function fetchPolicyEvents() {
  return apiGet<{ count: number; items: Record<string, unknown>[] }>("/api/policy/events");
}

export function fetchPolicyImpact(params: {
  event_code: string;
  category?: string;
  market?: string;
}): Promise<PolicyImpactPayload> {
  const query = new URLSearchParams({ event_code: params.event_code });
  if (params.category) query.set("category", params.category);
  if (params.market) query.set("market", params.market);
  return apiGet<PolicyImpactPayload>(`/api/policy/impact?${query.toString()}`);
}

export function fetchEvidenceLedger(): Promise<EvidenceLedgerPayload> {
  return apiGet<EvidenceLedgerPayload>("/api/evidence/ledger");
}

export function refreshPolicy(payload: Record<string, unknown> = {}) {
  return apiPost<PolicyRefreshResult>("/api/policy/refresh", payload);
}

export function fetchTradeReport(
  filters: {
    market?: string;
    risk_level?: string;
    limit?: number;
    offset?: number;
  } = {},
) {
  const params = new URLSearchParams();
  if (filters.market) params.set("market", filters.market);
  if (filters.risk_level) params.set("risk_level", filters.risk_level);
  if (filters.limit) params.set("limit", String(filters.limit));
  if (filters.offset) params.set("offset", String(filters.offset));
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return apiGet<TradeReportPayload>(`/api/trade/report${suffix}`);
}

export function fetchHsCode(category: string, market: string) {
  return apiGet<HsCode>(
    `/api/trade/hs-code?category=${encodeURIComponent(category)}&market=${encodeURIComponent(market)}`,
  );
}

export function fetchTradeCatalog() {
  return apiGet<CatalogPayload>("/api/catalog");
}

export function postTradeAutofill(payload: Record<string, unknown>) {
  return apiPost<{ data?: Record<string, unknown>; [key: string]: unknown }>(
    "/api/autofill",
    payload,
  );
}

export function postTradeAnalyze(payload: Record<string, unknown>) {
  return apiPost<{ data?: Record<string, unknown>; [key: string]: unknown }>(
    "/api/analyze",
    payload,
  );
}

export function uploadEda(file: File) {
  return apiUpload<EdaReport>("/api/eda", file);
}

export function importSellerMagic(file: File) {
  return apiUpload<SellerMagicImportResult>("/api/import/seller-magic", file);
}

export function exportVerdicts(payload: {
  rows: Record<string, unknown>[];
  webhook_url?: string;
}): Promise<VerdictExportResult> {
  return apiPost<VerdictExportResult>("/api/export/verdicts", payload);
}

export function fetchSearch(
  query: string,
  maxResults = 5,
  provider?: string,
) {
  const params = new URLSearchParams({ q: query, max_results: String(maxResults) });
  if (provider) params.set("provider", provider);
  return apiGet<SearchResult>(`/api/search?${params.toString()}`);
}

export async function fetchResearch(payload: Record<string, unknown>): Promise<ResearchResult> {
  const data = await apiPost<ResearchResult & { research?: ResearchResult }>(
    "/api/search/research",
    payload,
  );
  return data.research ?? data;
}

export function fetchCrawlerSignals(filters: DashboardQuery & { keyword?: string } = {}) {
  const params = new URLSearchParams();
  if (filters.category) params.set("category", filters.category);
  if (filters.market) params.set("market", filters.market);
  if (filters.keyword) params.set("keyword", filters.keyword);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return apiGet<CrawlerSignals>(`/api/crawler/signals${suffix}`);
}

export async function postCrawlerSignal(payload: Record<string, unknown>): Promise<CrawlerSignals> {
  const signal = await apiPost<Record<string, unknown>>("/api/crawler/signals", payload);
  if (Array.isArray(signal.combos)) {
    return signal as unknown as CrawlerSignals;
  }
  return {
    status: signal.fallback_used ? "fallback" : "ready",
    count: 1,
    combos: [signal],
  };
}

export function exportReport(payload: Record<string, unknown>) {
  return apiPostBlob("/api/export/report", payload);
}

export function exportLaunchReport(payload: Record<string, unknown>) {
  return apiPostBlob("/api/export/launch-report", payload);
}

function querySuffix(filters: DashboardQuery): string {
  const params = new URLSearchParams();
  if (filters.category) params.set("category", filters.category);
  if (filters.market) params.set("market", filters.market);
  if (filters.model) params.set("model", filters.model);
  return params.toString() ? `?${params.toString()}` : "";
}

function buildOfflineFourBrainBatch(
  items: Record<string, unknown>[],
): FourBrainBatchResult {
  const results = items.map((item) => ({
    ok: true,
    label: String(item.keyword || item.product || "方案"),
    result: buildOfflineFourBrain(item),
  }));
  return {
    items: results,
    summary: {
      total: results.length,
      ok: results.length,
      error: 0,
      use_ai: false,
    },
  };
}

function buildOfflineTradeDecision(
  params: {
    category: string;
    market: string;
    unit_price_usd: number;
    procurement_cost_cny: number;
    product_name?: string;
  },
  fxRate: number,
): TradeDecision {
  const fx = fxRate > 0 ? fxRate : DEFAULT_FX_RATE;
  const margin = Math.max(
    -15,
    ((params.unit_price_usd * fx - params.procurement_cost_cny * 1.35) /
      (params.unit_price_usd * fx)) *
      100,
  );
  return {
    category: params.category,
    market: params.market,
    category_name: params.category,
    market_name: params.market,
    product_name: params.product_name || "辣条（网红休闲零食）",
    risk_level: margin < 12 ? "high" : "medium",
    risk_message: "离线演示口径：基于内置快照估算，建议在线模式核对真实政策与成本。",
    actions: ["核对目标市场政策", "重算物流成本", "小批量试单"],
    effective_tariff_rate: 0.06,
    duty_usd_per_unit: 0.18,
    margin_pct: Math.round(margin * 10) / 10,
    raw_margin_pct: Math.round(margin * 10) / 10,
    best_logistics: "small_parcel",
    best_landed_cost_usd: Math.round((params.procurement_cost_cny / fx) * 1.35 * 100) / 100,
    feasibility_score: Math.round(Math.max(35, 85 - (margin < 12 ? 30 : 8))),
    compliance_recommendation: "离线快照无完整合规明细，在线运行后可查看。",
    hs_code: "8509.40",
    hs_description: "食品研磨机、搅拌器及水果或蔬菜榨汁器",
    hs_verified: false,
    freight_risk: "medium",
    sentiment_overall: "neutral",
    warnings: ["离线演示结果，请以在线 API 为准。"],
    clamped: false,
    policy_actions: [],
    policy_event_codes: [],
    ip_risk_level: "low",
    osint: { readiness: "pending", confidence: 0.5 },
    fx_rate: fx,
  };
}

function buildOfflineFourBrain(payload: Record<string, unknown>) {
  const keyword = String(payload.keyword || "辣条（网红休闲零食）");
  const market = String(payload.market || "us");
  return {
    keyword,
    market,
    verdict: "conditional",
    score: 72,
    summary: `基于离线快照对「${keyword}」×「${market}」进行规则引擎评估：需求与趋势信号中等偏强，证据维度不足，建议小批量试单并补充真实数据。`,
    dimensions: {
      demand: { label: "需求", score: 74, note: "搜索热度与销量指数中等偏上" },
      trend: { label: "趋势", score: 66, note: "近 90 日预测增速约 20%" },
      competition: { label: "竞争", score: 62, note: "竞争指数处于中低位" },
      margin: { label: "利润", score: 88, note: "毛利空间可接受" },
      compliance: { label: "合规", score: 72, note: "常规认证要求" },
      evidence: { label: "证据", score: 35, note: "离线快照未覆盖完整证据链" },
    },
    brains: {
      market: {
        id: "market",
        name: "市场分析师",
        score: 74,
        direction: "推荐",
        summary: `离线快照对「${keyword}」×「${market}」显示需求与趋势信号中等偏强，建议小批量试单并补充真实数据。`,
        conclusion_points: [
          "搜索热度与销量指数中等偏上",
          "近 90 日预测增速约 20%",
          "竞争指数处于中低位",
        ],
        evidence: ["离线快照：搜索热度与销量指数中等偏上", "离线快照：近 90 日预测增速约 20%"],
      },
      sentiment: {
        id: "sentiment",
        name: "舆情洞察官",
        score: 68,
        direction: "谨慎",
        summary: "用户反馈存在明确痛点，差异化机会集中在易用与耗材设计，建议先验证卖点。",
        conclusion_points: ["高频差评集中在使用便利性", "机会点包含耗材与维护成本", "离线快照未覆盖实时评论"],
        evidence: ["离线快照：高频差评集中在使用便利性", "离线快照：机会点包含耗材与维护成本"],
      },
      supply_chain: {
        id: "supply_chain",
        name: "供应链评估师",
        score: 72,
        direction: "推荐",
        summary: "到岸成本与交付周期处于可接受区间，供应链可行性偏积极，首单前需确认认证文件。",
        conclusion_points: ["到岸成本占比处于健康区间", "MOQ 与交付周期可接受", "认证文件需在首单前确认"],
        evidence: ["离线快照：到岸成本占比处于健康区间", "离线快照：MOQ 与交付周期可接受"],
      },
      finance: {
        id: "finance",
        name: "财务精算师",
        score: 71,
        direction: "推荐",
        summary: "毛利与现金流测算可支撑小批量试单，回本周期取决于实际广告效率。",
        conclusion_points: ["毛利空间可接受", "现金流可覆盖首批备货", "回本周期取决于广告效率"],
        evidence: ["离线快照：毛利空间可接受", "离线快照：现金流可覆盖首批备货"],
      },
    },
    research: {
      disabled: true,
      summary: "离线演示未进行联网检索，结论仅基于内置快照。",
      sources: [],
    },
    generated_at: "offline-engine-v1",
  };
}
