import type {
  DashboardData,
  ExamplePreset,
  ForecastRow,
  HistoryRow,
  Recommendation,
} from "@/shared/api/types";

export interface DashboardFilters {
  category?: string;
  market?: string;
  model?: string;
}

export function filterHistory(rows: HistoryRow[], filters: DashboardFilters): HistoryRow[] {
  return rows.filter(
    (row) =>
      (!filters.category || row.category === filters.category) &&
      (!filters.market || row.market === filters.market),
  );
}

export function filterForecast(rows: ForecastRow[], filters: DashboardFilters): ForecastRow[] {
  return rows.filter(
    (row) =>
      (!filters.category || row.category === filters.category) &&
      (!filters.market || row.market === filters.market) &&
      (!filters.model || row.model === filters.model),
  );
}

export function filterRecommendations(
  rows: Recommendation[],
  _filters: DashboardFilters,
): Recommendation[] {
  return recommendableTop(rows, 20);
}

/**
 * 只看板展示用的推荐过滤：候选池为全部 1980 组合，按六维评分降序稳定排序，
 * 与后端 /api/dashboard-data 的 recommendations 口径一致（六维分 → 增长 → 趋势 → 字典序）。
 * 在线与离线快照都走同一排序，前端重排 rank，避免受输入文件原始顺序影响。
 */
export function recommendableTop(rows: Recommendation[], limit = 20): Recommendation[] {
  return rows
    .filter(
      (row) => row.verdict !== "No-Go" && Number.isFinite(Number(row.six_dimension_score)),
    )
    .sort((a, b) => {
      const scoreDiff = Number(b.six_dimension_score) - Number(a.six_dimension_score);
      if (scoreDiff !== 0) return scoreDiff;
      const growthDiff = Number(b.forecast_growth) - Number(a.forecast_growth);
      if (growthDiff !== 0) return growthDiff;
      const trendDiff = Number(b.search_trend) - Number(a.search_trend);
      if (trendDiff !== 0) return trendDiff;
      return `${a.category}:${a.market}`.localeCompare(`${b.category}:${b.market}`);
    })
    .slice(0, limit)
    .map((row, index) => ({ ...row, rank: index + 1 }));
}

export function dashboardExampleFilters(
  examples: ExamplePreset[],
  id: string,
): { category: string; market: string } | null {
  const preset = examples.find((item) => item.id === id);
  if (!preset?.category || !preset.market) return null;
  return { category: String(preset.category), market: String(preset.market) };
}

export function filterDashboardData(
  data: DashboardData,
  filters: DashboardFilters,
): DashboardData {
  return {
    ...data,
    history: filterHistory(data.history ?? [], filters),
    forecast: filterForecast(data.forecast ?? [], filters),
    recommendations: filterRecommendations(data.recommendations ?? [], filters),
    metrics: {
      baseline: (data.metrics?.baseline ?? []).filter(
        (item) =>
          (!filters.category || item.category === filters.category) &&
          (!filters.market || item.market === filters.market),
      ),
      advanced: (data.metrics?.advanced ?? []).filter(
        (item) =>
          (!filters.category || item.category === filters.category) &&
          (!filters.market || item.market === filters.market),
      ),
      statsforecast: (data.metrics?.statsforecast ?? []).filter(
        (item) =>
          (!filters.category || item.category === filters.category) &&
          (!filters.market || item.market === filters.market),
      ),
    },
  };
}

export function categoryOptions(data?: DashboardData) {
  const map = data?.categories ?? {};
  return Object.entries(map).map(([value, label]) => ({ value, label }));
}

export function marketOptions(data?: DashboardData) {
  const map = data?.markets ?? {};
  return Object.entries(map).map(([value, label]) => ({ value, label }));
}

export function modelOptions(data?: DashboardData) {
  const map = data?.models ?? {};
  return Object.entries(map).map(([value, label]) => ({ value, label }));
}

export function average(values: number[]): number {
  if (!values.length) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

export function bestForecastModel(
  metrics: DashboardData["metrics"] | undefined,
  category?: string,
  market?: string,
): string {
  const rows = [
    ...(metrics?.baseline ?? []),
    ...(metrics?.advanced ?? []),
  ].filter(
    (row) =>
      (!category || row.category === category) &&
      (!market || row.market === market),
  );
  const finite = rows.filter((row) => Number.isFinite(Number(row.mape)));
  if (!finite.length) return "lightgbm_advanced";
  const byModel = new Map<string, { sum: number; count: number }>();
  for (const row of finite) {
    const current = byModel.get(row.model) ?? { sum: 0, count: 0 };
    current.sum += Number(row.mape);
    current.count += 1;
    byModel.set(row.model, current);
  }
  const best = [...byModel.entries()].sort(
    (a, b) => a[1].sum / a[1].count - b[1].sum / b[1].count,
  )[0];
  return best?.[0] ?? "lightgbm_advanced";
}
