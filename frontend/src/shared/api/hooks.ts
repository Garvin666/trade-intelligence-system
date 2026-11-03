import { useMutation, useQuery } from "@tanstack/react-query";
import {
  exportReport,
  exportVerdicts,
  fetchAiConfig,
  fetchAnomalies,
  fetchControlMetrics,
  fetchControlRunStatus,
  getDataStatus,
  fetchEngineeringStatus,
  fetchEnvCheck,
  fetchExamples,
  fetchEvidenceLedger,
  fetchFeedbackList,
  fetchForecast,
  fetchGlobeMarketPicks,
  fetchHealth,
  fetchHistory,
  fetchHsCode,
  fetchHsCodes,
  fetchJobs,
  fetchMarketCompare,
  fetchMarketIntel,
  fetchModelMetrics,
  fetchPolicyImpact,
  fetchPolicyEvents,
  fetchRecommendations,
  fetchScoringWeights,
  fetchSuppliers,
  fetchSystemEval,
  fetchTradeCatalog,
  fetchTradeReport,
  postFeedback,
  refreshPolicy,
  saveAiConfig,
  saveScoringWeights,
  startControlRun,
  startJob,
  stopJob,
  testAiConnection,
  testSearchConnection,
  uploadEda,
  fetchDashboardData,
  importSellerMagic,
  postFourBrainBatch,
  type DashboardQuery,
} from "./client";
import { IS_OFFLINE } from "./offline";
import type {
  AiConfigPayload,
  CategoryMap,
  DashboardData,
} from "./types";
import { filterDashboardData } from "@/entities/dashboard/model";

export function useDashboardData(query: DashboardQuery) {
  return useQuery({
    queryKey: ["dashboard-data", query.category, query.market, query.model, IS_OFFLINE],
    queryFn: async () => {
      if (IS_OFFLINE) {
        const data = window.__TRADE_INTEL_OFFLINE__;
        if (!data) throw new Error("离线快照缺失");
        return filterDashboardData(data, query);
      }
      return fetchDashboardData(query);
    },
    staleTime: IS_OFFLINE ? Infinity : 60_000,
    gcTime: IS_OFFLINE ? Infinity : 300_000,
    placeholderData: (previous: DashboardData | undefined) => previous,
  });
}

export function useDataStatus() {
  return useQuery({
    queryKey: ["data-status", IS_OFFLINE],
    queryFn: getDataStatus,
    enabled: !IS_OFFLINE,
    staleTime: 30_000,
  });
}

export interface Catalog {
  categories: CategoryMap;
  markets: CategoryMap;
  models: CategoryMap;
}

export function useCatalog() {
  return useQuery({
    queryKey: ["catalog", IS_OFFLINE],
    queryFn: async (): Promise<Catalog> => {
      if (IS_OFFLINE) {
        const data = window.__TRADE_INTEL_OFFLINE__;
        return {
          categories: data?.categories ?? {},
          markets: data?.markets ?? {},
          models: data?.models ?? {},
        };
      }
      const [categories, markets, models] = await Promise.all([
        fetch("/api/categories").then((r) => r.json()),
        fetch("/api/markets").then((r) => r.json()),
        fetch("/api/models").then((r) => r.json()),
      ]);
      return {
        categories: categories as CategoryMap,
        markets: markets as CategoryMap,
        models: models as CategoryMap,
      };
    },
    staleTime: IS_OFFLINE ? Infinity : 5 * 60_000,
  });
}

export function useSystemStatus() {
  return useQuery({
    queryKey: ["system-status", IS_OFFLINE],
    queryFn: async () => {
      const [health, engineering, systemEval, suppliers] = await Promise.all([
        fetchHealth(),
        fetchEngineeringStatus(),
        fetchSystemEval(),
        fetchSuppliers(),
      ]);
      return { health, engineering, systemEval, suppliers };
    },
    enabled: !IS_OFFLINE,
    staleTime: 30_000,
  });
}

export function useEnvCheck() {
  return useQuery({
    queryKey: ["env-check", IS_OFFLINE],
    queryFn: () => fetchEnvCheck(),
    enabled: !IS_OFFLINE,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
}

export function useJobs() {
  return useQuery({
    queryKey: ["jobs", IS_OFFLINE],
    queryFn: fetchJobs,
    enabled: !IS_OFFLINE,
    refetchInterval: (query) =>
      query.state.data?.items.some((job) => job.status === "running") ? 2000 : false,
    staleTime: 10_000,
  });
}

export function useStartJob() {
  return useMutation({
    mutationFn: ({ name, payload }: { name: string; payload?: Record<string, unknown> }) =>
      startJob(name, payload),
  });
}

export function useStopJob() {
  return useMutation({
    mutationFn: (name: string) => stopJob(name),
  });
}

export function useAiConfig() {
  return useQuery({
    queryKey: ["ai-config", IS_OFFLINE],
    queryFn: fetchAiConfig,
    enabled: !IS_OFFLINE,
    staleTime: 60_000,
  });
}

export function useSaveAiConfig() {
  return useMutation({
    mutationFn: (payload: AiConfigPayload) => saveAiConfig(payload),
  });
}

export function useTestAiConnection() {
  return useMutation({ mutationFn: testAiConnection });
}

export function useTestSearchConnection() {
  return useMutation({ mutationFn: testSearchConnection });
}

export function useControlMetrics() {
  return useQuery({
    queryKey: ["control-metrics", IS_OFFLINE],
    queryFn: fetchControlMetrics,
    enabled: !IS_OFFLINE,
    staleTime: 60_000,
  });
}

export function useControlRunStatus() {
  return useQuery({
    queryKey: ["control-run-status", IS_OFFLINE],
    queryFn: fetchControlRunStatus,
    enabled: !IS_OFFLINE,
    refetchInterval: (query) =>
      query.state.data?.status === "running" ? 2000 : false,
    staleTime: 10_000,
  });
}

export function useStartControlRun() {
  return useMutation({ mutationFn: startControlRun });
}

export function useFeedbackList() {
  return useQuery({
    queryKey: ["feedback", IS_OFFLINE],
    queryFn: fetchFeedbackList,
    enabled: !IS_OFFLINE,
    staleTime: 30_000,
  });
}

export function usePostFeedback() {
  return useMutation({ mutationFn: postFeedback });
}

export function useScoringWeights() {
  return useQuery({
    queryKey: ["scoring-weights", IS_OFFLINE],
    queryFn: fetchScoringWeights,
    enabled: !IS_OFFLINE,
    staleTime: 30_000,
  });
}

export function useSaveScoringWeights() {
  return useMutation({ mutationFn: saveScoringWeights });
}

export function useMarketIntel(filters: DashboardQuery) {
  return useQuery({
    queryKey: ["market-intel", filters.category, filters.market, IS_OFFLINE],
    queryFn: () => fetchMarketIntel(filters),
    enabled: !IS_OFFLINE,
    staleTime: 60_000,
    placeholderData: (previous) => previous,
  });
}

export function useMarketCompare(filters: DashboardQuery) {
  return useQuery({
    queryKey: ["market-compare", filters.category, IS_OFFLINE],
    queryFn: () => fetchMarketCompare(filters),
    enabled: !IS_OFFLINE,
    staleTime: 60_000,
  });
}

export function useModelMetrics(filters: DashboardQuery) {
  return useQuery({
    queryKey: ["model-metrics", filters.model, filters.category, filters.market, IS_OFFLINE],
    queryFn: () => fetchModelMetrics(filters),
    enabled: !IS_OFFLINE,
    staleTime: 60_000,
  });
}

export function useForecast(filters: DashboardQuery) {
  return useQuery({
    queryKey: ["forecast", filters.model, filters.category, filters.market, IS_OFFLINE],
    queryFn: () => fetchForecast(filters),
    enabled: !IS_OFFLINE,
    staleTime: 60_000,
  });
}

export function useHistory(filters: DashboardQuery) {
  return useQuery({
    queryKey: ["history", filters.category, filters.market, IS_OFFLINE],
    queryFn: () => fetchHistory(filters),
    enabled: !IS_OFFLINE,
    staleTime: 60_000,
  });
}

export function useRecommendations(
  filters: DashboardQuery & { include_no_go?: boolean; top?: number },
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: ["recommendations", filters.category, filters.market, filters.include_no_go, filters.top, IS_OFFLINE],
    queryFn: () => fetchRecommendations(filters),
    enabled: options?.enabled ?? true,
    staleTime: 60_000,
  });
}

export function useGlobeMarketPicks(
  marketIds: string[],
  options?: { enabled?: boolean },
) {
  return useQuery({
    queryKey: ["globe-market-picks", marketIds.join(","), IS_OFFLINE],
    queryFn: () => fetchGlobeMarketPicks(marketIds),
    enabled: options?.enabled ?? true,
    staleTime: 60_000,
    gcTime: 300_000,
  });
}

export function usePolicyEvents() {
  return useQuery({
    queryKey: ["policy-events", IS_OFFLINE],
    queryFn: fetchPolicyEvents,
    enabled: !IS_OFFLINE,
    staleTime: 60_000,
  });
}

export function usePolicyImpact(
  params: { event_code: string; category?: string; market?: string },
  enabled = true,
) {
  return useQuery({
    queryKey: ["policy-impact", params.event_code, params.category, params.market, IS_OFFLINE],
    queryFn: () => fetchPolicyImpact(params),
    enabled: !IS_OFFLINE && enabled && Boolean(params.event_code),
    staleTime: 60_000,
  });
}

export function useEvidenceLedger() {
  return useQuery({
    queryKey: ["evidence-ledger", IS_OFFLINE],
    queryFn: fetchEvidenceLedger,
    enabled: !IS_OFFLINE,
    staleTime: 60_000,
  });
}

export function useRefreshPolicy() {
  return useMutation({ mutationFn: refreshPolicy });
}

export function useTradeReport(
  filters: { market?: string; risk_level?: string } = {},
) {
  return useQuery({
    queryKey: ["trade-report", filters.market, filters.risk_level, IS_OFFLINE],
    queryFn: () =>
      fetchTradeReport({
        market: filters.market,
        risk_level: filters.risk_level,
        limit: 100,
      }),
    enabled: !IS_OFFLINE,
    staleTime: 60_000,
  });
}

export function useTradeCatalog() {
  return useQuery({
    queryKey: ["trade-catalog", IS_OFFLINE],
    queryFn: fetchTradeCatalog,
    enabled: !IS_OFFLINE,
    staleTime: 5 * 60_000,
  });
}

export function useExamples() {
  return useQuery({
    queryKey: ["examples", IS_OFFLINE],
    queryFn: fetchExamples,
    staleTime: IS_OFFLINE ? Infinity : 5 * 60_000,
  });
}

export function useAnomalies() {
  return useQuery({
    queryKey: ["anomalies", IS_OFFLINE],
    queryFn: fetchAnomalies,
    enabled: !IS_OFFLINE,
    staleTime: 60_000,
  });
}

export function useHsCodesSearch(
  params: { q?: string; category?: string; market?: string },
  enabled = false,
) {
  return useQuery({
    queryKey: ["hs-codes-search", params.q, params.category, params.market, IS_OFFLINE],
    queryFn: () => fetchHsCodes(params),
    enabled: !IS_OFFLINE && enabled,
    staleTime: 60_000,
  });
}

export function useFourBrainBatch() {
  return useMutation({
    mutationFn: postFourBrainBatch,
  });
}

export function useHsCode(category: string, market: string, enabled = false) {
  return useQuery({
    queryKey: ["hs-code", category, market, IS_OFFLINE],
    queryFn: () => fetchHsCode(category, market),
    enabled: !IS_OFFLINE && enabled && Boolean(category && market),
    staleTime: 60_000,
  });
}

export function useEdaUpload() {
  return useMutation({ mutationFn: uploadEda });
}

export function useExportReport() {
  return useMutation({
    mutationFn: exportReport,
  });
}

export function useExportVerdicts() {
  return useMutation({ mutationFn: exportVerdicts });
}

export function useSellerMagicImport() {
  return useMutation({ mutationFn: importSellerMagic });
}
