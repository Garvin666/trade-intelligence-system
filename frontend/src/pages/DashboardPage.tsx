import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useDashboardData, useExamples, useRecommendations } from "@/shared/api/hooks";
import { useRefreshPolicy } from "@/shared/api/hooks";
import { useTradeIntelStore } from "@/shared/store/trade-intel";
import { Skeleton } from "@/shared/ui/skeleton";
import { GlassCard } from "@/shared/ui/glass-card";
import { Button } from "@/shared/ui/button";
import { Select } from "@/shared/ui/select";
import { PageTurnTabs } from "@/shared/ui/page-turn-tabs";
import { AgentPageShell } from "@/widgets/AgentPageShell";
import { MetricsGrid } from "@/widgets/MetricsGrid";
import { DataStatusStrip } from "@/widgets/DataStatusStrip";
import { TrendChart } from "@/features/dashboard/TrendChart";
import { ForecastChart } from "@/features/dashboard/ForecastChart";
import { RecommendationTable } from "@/features/dashboard/RecommendationTable";
import { PolicyPanel } from "@/features/dashboard/PolicyPanel";
import { MarketIntelPanel } from "@/features/dashboard/MarketIntelPanel";
import { ModelMetricsPanel } from "@/features/dashboard/ModelMetricsPanel";
import { ExportReportButton } from "@/features/dashboard/ExportReportButton";
import { VerdictExportButton } from "@/features/dashboard/VerdictExportButton";
import { AnomalyPanel } from "@/features/dashboard/AnomalyPanel";
import {
  IntegrationPanel,
  OfflineIntegrationPanel,
} from "@/features/plans/IntegrationPanel";
import { useTransitionNavigate } from "@/widgets/RouteTransition";
import type { Recommendation } from "@/shared/api/types";
import { categoryName, marketName } from "@/shared/lib/names";
import {
  bestForecastModel,
  dashboardExampleFilters,
  recommendableTop,
} from "@/entities/dashboard/model";
import { Badge } from "@/shared/ui/badge";
import { Progress } from "@/shared/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/ui/table";
import {
  BrainCircuit,
  Eye,
  LayoutDashboard,
  ListPlus,
  RefreshCw,
  Ship,
  Wand2,
  X,
} from "lucide-react";
import { IS_OFFLINE } from "@/shared/api/offline";
import { RouteStatusBar } from "@/shared/motion/RouteStatusBar";

export default function DashboardPage() {
  const [searchParams] = useSearchParams();
  const activeTab = searchParams.get("tab") ?? "overview";
  const filters = useTradeIntelStore((state) => state.filters);
  const setFilters = useTradeIntelStore((state) => state.setFilters);
  const setSelectionDraft = useTradeIntelStore((state) => state.setSelectionDraft);
  const addToWatchlist = useTradeIntelStore((state) => state.addToWatchlist);
  const watchlist = useTradeIntelStore((state) => state.watchlist);
  const { data, isLoading, isError, error } = useDashboardData({
    category: filters.category,
    market: filters.market,
  });
  const refreshPolicy = useRefreshPolicy();
  const { data: examples } = useExamples();
  const [exampleId, setExampleId] = useState("dashboard_latiao_us");
  const [detailRow, setDetailRow] = useState<Recommendation | null>(null);
  const [compareRows, setCompareRows] = useState<Recommendation[]>([]);
  const [showNoGo, setShowNoGo] = useState(false);
  const transitionNavigate = useTransitionNavigate();
  const comboLabel = [
    filters.category ? categoryName(filters.category) : "",
    filters.market ? marketName(filters.market) : "",
  ]
    .filter(Boolean)
    .join(" × ") || "全部组合";
  const topRecommendations = useMemo(
    () => recommendableTop(data?.recommendations ?? []),
    [data?.recommendations],
  );
  const primaryModel = useMemo(
    () => bestForecastModel(data?.metrics, filters.category, filters.market),
    [data?.metrics, filters.category, filters.market],
  );

  // 开启"显示 No-Go 组合"时，向后端请求含 No-Go 的推荐行（含判定原因），
  // 与看板 Top 20 合并展示；默认关闭避免 55MB 全量数据外的额外请求。
  const { data: noGoData, isLoading: noGoLoading } = useRecommendations(
    {
      include_no_go: true,
      top: 20,
    },
    { enabled: showNoGo && !IS_OFFLINE },
  );

  const tableRows = useMemo(() => {
    if (!showNoGo) return topRecommendations;
    const items = (noGoData?.items ?? []) as unknown as Recommendation[];
    if (!items.length) return topRecommendations;
    return items.map((item, index) => ({ ...item, rank: index + 1 }));
  }, [showNoGo, noGoData, topRecommendations]);

  const dashboardExamples = useMemo(
    () => examples?.dashboard ?? [],
    [examples],
  );
  const exampleOptions = useMemo(
    () =>
      dashboardExamples.map((item) => ({
        value: String(item.id),
        label: String(item.label ?? item.id),
      })),
    [dashboardExamples],
  );

  const changeExample = (value: string) => {
    setExampleId(value);
    const next = dashboardExampleFilters(dashboardExamples, value);
    if (!next) return;
    setFilters(next);
    setDetailRow(null);
  };

  const applyExample = () => {
    changeExample(exampleId);
  };

  const startFourBrain = (row: Recommendation) => {
    setSelectionDraft({
      label: `${categoryName(row.category)} × ${marketName(row.market)}`,
      keyword: categoryName(row.category),
      category: row.category,
      market: row.market,
      verdict: row.verdict,
      score: row.six_dimension_score,
    });
    transitionNavigate("/workbench");
  };

  const startTrade = (row: Recommendation) => {
    setSelectionDraft({
      label: `${categoryName(row.category)} × ${marketName(row.market)}`,
      category: row.category,
      market: row.market,
      price: 39.9,
      procurement_cost_cny: 98,
    });
    transitionNavigate("/trade");
  };

  const watchRow = (row: Recommendation) => {
    addToWatchlist({
      id: `${row.category}-${row.market}`,
      label: `${categoryName(row.category)} × ${marketName(row.market)}`,
      category: row.category,
      market: row.market,
      keyword: categoryName(row.category),
      verdict: row.verdict,
      score: row.six_dimension_score,
      createdAt: new Date().toISOString(),
    });
  };

  const toggleCompare = (row: Recommendation) => {
    setCompareRows((prev) => {
      if (prev.some((item) => `${item.category}-${item.market}` === `${row.category}-${row.market}`)) {
        return prev.filter((item) => `${item.category}-${item.market}` !== `${row.category}-${row.market}`);
      }
      return [...prev, row].slice(0, 5);
    });
  };

  return (
    <AgentPageShell
      icon={LayoutDashboard}
      title="选品看板"
      description="132 品类 × 15 市场 · 六维评分 · Go/No-Go 判定"
    >
      <div className="entrance-reveal" style={{ animationDelay: "0.42s" }}>
        <RouteStatusBar
          items={[
            { label: "数据更新", value: "实时快照", tone: "green" },
            { label: "预测基线", value: "3 模型", tone: "cyan" },
            { label: "证据闸", value: "开启", tone: "amber" },
            { label: "推荐组合", value: "1980", tone: "violet" },
          ]}
        />
      </div>
      <div
        className="entrance-reveal mt-6 grid gap-4"
        style={{ animationDelay: "0.68s" }}
      >
        <DataStatusStrip status={data?.data_status} />
        {isError && (
          <GlassCard className="border-danger/20 bg-danger/10">
            <p className="text-sm text-red-200">
              {error instanceof Error ? error.message : "看板数据加载失败，请确认后端已启动。"}
            </p>
          </GlassCard>
        )}
      </div>

      <div className="entrance-reveal" style={{ animationDelay: "0.76s" }}>
        <PageTurnTabs
          className="mt-6"
          key={activeTab}
          defaultValue={activeTab}
          listClassName="w-full justify-start overflow-x-auto"
          tabs={[
          {
            value: "overview",
            label: "概览",
            content:
              isLoading && !data ? (
                <div className="grid gap-4">
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
                    {[0, 1, 2, 3].map((item) => (
                      <Skeleton key={item} className="h-28" />
                    ))}
                  </div>
                  <Skeleton className="h-80" />
                  <Skeleton className="h-80" />
                </div>
              ) : (
                data && (
                  <>
                    <div className="mb-4 flex flex-wrap items-center justify-end gap-2">
                      {!IS_OFFLINE && (
                        <>
                          <Select
                            value={exampleId}
                            onValueChange={changeExample}
                            options={exampleOptions}
                            ariaLabel="选择看板示例"
                            className="w-56"
                          />
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={applyExample}
                          >
                            <Wand2 className="h-4 w-4" />
                            填充示例
                          </Button>
                        </>
                      )}
                      {!IS_OFFLINE && (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={refreshPolicy.isPending}
                          onClick={() => refreshPolicy.mutate({})}
                        >
                          <RefreshCw className="h-4 w-4" />
                          {refreshPolicy.isPending ? "刷新中..." : "刷新政策雷达"}
                        </Button>
                      )}
                      <ExportReportButton
                        filters={filters}
                        recommendations={topRecommendations}
                      />
                      <VerdictExportButton rows={topRecommendations} />
                    </div>
                    <MetricsGrid data={data} />

                    <div className="mt-6 grid gap-4 xl:grid-cols-2">
                      <GlassCard
                        className="min-w-0"
                        title="多源热度趋势"
                        description="销量指数 / 搜索热度 / 出口金额归一化对比"
                      >
                        <TrendChart rows={data.history ?? []} />
                      </GlassCard>
                      <GlassCard
                        className="min-w-0"
                        title={`${comboLabel} · 销售预测`}
                        description="Prophet / LightGBM 双模型 90 天预测 · 主预测 = 回测 MAPE 更优模型"
                      >
                        <ForecastChart
                          history={data.history ?? []}
                          forecast={data.forecast ?? []}
                          modelsOrder={data.models_order}
                          primaryModel={primaryModel}
                        />
                      </GlassCard>
                    </div>

                    <div className="mt-6 grid gap-4 xl:grid-cols-[1.6fr_1fr]">
                      <GlassCard
                        className="min-w-0"
                        title="Top 20 推荐组合"
                        description={
                          showNoGo
                            ? "已包含 No-Go 组合（红色标记，附判定原因）"
                            : "六维评分与 Go/No-Go 判定"
                        }
                      >
                        <div className="mb-3 flex flex-wrap items-center justify-end gap-2">
                          {showNoGo && noGoLoading && (
                            <span className="text-xs text-slate-500">加载 No-Go 数据中…</span>
                          )}
                          <Button
                            size="sm"
                            variant={showNoGo ? "secondary" : "outline"}
                            onClick={() => setShowNoGo((value) => !value)}
                          >
                            <Eye className="h-3.5 w-3.5" />
                            {showNoGo ? "隐藏 No-Go" : "显示 No-Go 组合"}
                          </Button>
                        </div>
                        <RecommendationTable
                          rows={tableRows}
                          watchedIds={watchlist.map((item) => `${item.category}-${item.market}`)}
                          onOpenDetail={setDetailRow}
                          onFourBrain={startFourBrain}
                          onTrade={startTrade}
                          onWatch={watchRow}
                          onShowNoGo={() => setShowNoGo(true)}
                        />
                      </GlassCard>
                      <GlassCard
                        className="min-w-0"
                        title="政策雷达"
                        description="官方源优先的关税与监管事件"
                      >
                        <PolicyPanel events={data.policy_events ?? []} />
                      </GlassCard>
                    </div>

                    <div className="mt-6">
                      <AnomalyPanel />
                    </div>

                    {detailRow && (
                      <div className="mt-6">
                        <RecommendationDetailCard
                          row={detailRow}
                          onClose={() => setDetailRow(null)}
                          onCompare={() => toggleCompare(detailRow)}
                          onFourBrain={() => startFourBrain(detailRow)}
                          onTrade={() => startTrade(detailRow)}
                        />
                      </div>
                    )}

                    {compareRows.length >= 2 && (
                      <div className="mt-6">
                        <CompareCard
                          rows={compareRows}
                          onRemove={(row) => toggleCompare(row)}
                          onClear={() => setCompareRows([])}
                        />
                      </div>
                    )}
                  </>
                )
              ),
          },
          {
            value: "data-depth",
            label: "数据纵深",
            content: (
              <div className="grid gap-4">
                {IS_OFFLINE ? (
                  <OfflineIntegrationPanel />
                ) : (
                  <IntegrationPanel showSystemLink={false} />
                )}
                <MarketIntelPanel filters={filters} />
                <ModelMetricsPanel filters={filters} />
              </div>
            ),
          },
          ]}
        />
      </div>
    </AgentPageShell>
  );
}

function RecommendationDetailCard({
  row,
  onClose,
  onCompare,
  onFourBrain,
  onTrade,
}: {
  row: Recommendation;
  onClose: () => void;
  onCompare: () => void;
  onFourBrain: () => void;
  onTrade: () => void;
}) {
  const dimensions = [
    { label: "需求", value: row.dimension_demand, tone: "cyan" as const },
    { label: "趋势", value: row.dimension_trend, tone: "cyan" as const },
    { label: "竞争", value: row.dimension_competition, tone: "amber" as const },
    { label: "利润", value: row.dimension_margin, tone: "cyan" as const },
    { label: "合规", value: row.dimension_compliance, tone: "amber" as const },
    { label: "证据", value: row.dimension_evidence, tone: "green" as const },
  ];
  return (
    <GlassCard
      title={`推荐详情：${categoryName(row.category)} × ${marketName(row.market)}`}
      description={row.decision_reason || "六维评分与判定依据"}
      strong
    >
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Badge tone={row.verdict.toLowerCase().includes("go") ? "green" : "amber"}>
          {row.verdict}
        </Badge>
        <span className="tabular text-lg font-extrabold text-accent">
          {row.six_dimension_score.toFixed(1)} / 100
        </span>
        <div className="ml-auto flex items-center gap-2">
          <Button size="sm" variant="secondary" onClick={onCompare}>
            <ListPlus className="h-3.5 w-3.5" />
            加入对比
          </Button>
          <Button size="sm" variant="outline" onClick={onFourBrain}>
            <BrainCircuit className="h-3.5 w-3.5" />
            四脑立项
          </Button>
          <Button size="sm" variant="outline" onClick={onTrade}>
            <Ship className="h-3.5 w-3.5" />
            贸易决策
          </Button>
          <Button size="icon" variant="ghost" onClick={onClose} aria-label="关闭详情">
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {dimensions.map((item) => (
          <div key={item.label} className="glass-soft p-3">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-slate-300">{item.label}</span>
              <span className="tabular text-accent">{item.value.toFixed(1)}</span>
            </div>
            <Progress value={item.value} tone={item.tone} className="mt-2" />
          </div>
        ))}
      </div>
      <div className="mt-4 grid gap-2 text-sm text-slate-300 sm:grid-cols-2">
        <div className="glass-soft p-3">
          预测增长 <span className="tabular text-emerald-300">{row.forecast_growth.toFixed(1)}%</span>
        </div>
        <div className="glass-soft p-3">
          搜索趋势 <span className="tabular text-accent">{row.search_trend.toFixed(1)}%</span>
        </div>
        <div className="glass-soft p-3">
          竞争度 <span className="tabular text-amber-200">{row.competition.toFixed(1)}</span>
        </div>
        <div className="glass-soft p-3">
          评论增长 <span className="tabular text-emerald-300">{row.review_growth.toFixed(1)}%</span>
        </div>
      </div>
      <p className="mt-4 text-xs leading-5 text-slate-500">{row.reasons}</p>
    </GlassCard>
  );
}

function CompareCard({
  rows,
  onRemove,
  onClear,
}: {
  rows: Recommendation[];
  onRemove: (row: Recommendation) => void;
  onClear: () => void;
}) {
  return (
    <GlassCard
      title={`组合对比（${rows.length}/5）`}
      description="六维评分与关键指标横向比较"
      strong
    >
      <div className="mb-3 flex justify-end">
        <Button size="sm" variant="ghost" onClick={onClear}>
          <X className="h-3.5 w-3.5" />
          清空对比
        </Button>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>组合</TableHead>
            <TableHead>六维评分</TableHead>
            <TableHead>判定</TableHead>
            <TableHead>增长</TableHead>
            <TableHead>趋势</TableHead>
            <TableHead>竞争</TableHead>
            <TableHead>证据</TableHead>
            <TableHead></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={`${row.category}-${row.market}`}>
              <TableCell className="font-semibold text-white">
                {categoryName(row.category)} × {marketName(row.market)}
              </TableCell>
              <TableCell className="tabular text-accent">
                {row.six_dimension_score.toFixed(1)}
              </TableCell>
              <TableCell>
                <Badge tone={row.verdict.toLowerCase().includes("go") ? "green" : "amber"}>
                  {row.verdict}
                </Badge>
              </TableCell>
              <TableCell className="tabular">{row.forecast_growth.toFixed(1)}%</TableCell>
              <TableCell className="tabular">{row.search_trend.toFixed(1)}%</TableCell>
              <TableCell className="tabular">{row.competition.toFixed(1)}</TableCell>
              <TableCell className="tabular">{row.dimension_evidence.toFixed(0)}</TableCell>
              <TableCell>
                <Button
                  size="icon"
                  variant="ghost"
                  onClick={() => onRemove(row)}
                  aria-label={`移除 ${categoryName(row.category)}`}
                >
                  <X className="h-3.5 w-3.5" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </GlassCard>
  );
}
