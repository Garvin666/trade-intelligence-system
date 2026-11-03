import { useLayoutEffect, useMemo } from "react";
import {
  ArrowRight,
  BrainCircuit,
  FolderKanban,
  Layers,
  Ship,
  Star,
  Trash2,
  Wand2,
} from "lucide-react";
import { useExamples } from "@/shared/api/hooks";
import { IS_OFFLINE } from "@/shared/api/offline";
import { useTradeIntelStore } from "@/shared/store/trade-intel";
import { seedDemoIfEmpty } from "@/features/plans/demoSeed";
import {
  IntegrationPanel,
  OfflineIntegrationPanel,
} from "@/features/plans/IntegrationPanel";
import type { StatusTone } from "@/features/plans/integrationStatus";
import { useTransitionNavigate } from "@/widgets/RouteTransition";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { GlassCard } from "@/shared/ui/glass-card";
import { Select } from "@/shared/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/ui/table";
import { Page3DScene } from "@/shared/motion/Page3DScene";
import { AgentPageShell } from "@/widgets/AgentPageShell";

export default function PlansPage() {
  const transitionNavigate = useTransitionNavigate();
  const { data: examples } = useExamples();
  const {
    selectionDraft,
    watchlist,
    scenarios,
    batchRuns,
    setSelectionDraft,
    removeFromWatchlist,
    removeScenario,
    removeBatchRun,
  } = useTradeIntelStore();

  // 全新演示环境首次进入方案中心时，四个区块全空显得页面空旷；
  // 预置与系统真实数据一致的演示内容（只执行一次，删光后不会重复填充）。
  useLayoutEffect(() => {
    const store = useTradeIntelStore;
    seedDemoIfEmpty(
      () => store.getState(),
      {
        setSelectionDraft: (draft) => store.getState().setSelectionDraft(draft),
        addToWatchlist: (item) => store.getState().addToWatchlist(item),
        addScenario: (scenario) => store.getState().addScenario(scenario),
        saveBatchRun: (run) => store.getState().saveBatchRun(run),
        markDemoSeeded: () => store.getState().markDemoSeeded(),
      },
    );
  }, []);

  const workflowExamples = useMemo(
    () => examples?.workflow ?? [],
    [examples],
  );
  const workflowOptions = useMemo(
    () =>
      workflowExamples.map((item) => ({
        value: String(item.id),
        label: String(item.label ?? item.id),
      })),
    [workflowExamples],
  );

  const applyWorkflowExample = () => {
    const preset = workflowExamples[0];
    const plan = (preset?.plan ?? {}) as Record<string, unknown>;
    if (!Object.keys(plan).length) return;
    setSelectionDraft({
      keyword: String(plan.keyword ?? ""),
      category: String(plan.category ?? "cn_latiao"),
      market: String(plan.market ?? "us"),
      price: typeof plan.price === "number" ? Number(plan.price) : 4.9,
      procurement_cost_cny:
        typeof plan.procurement_cost_cny === "number"
          ? Number(plan.procurement_cost_cny)
          : 12,
      budget: typeof plan.budget === "number" ? Number(plan.budget) : 20000,
      target_margin:
        typeof plan.target_margin === "number" ? Number(plan.target_margin) : 0.35,
      label: String(preset?.label ?? "示例方案"),
    });
  };

  const continueWorkbench = () => {
    if (!selectionDraft) return;
    transitionNavigate("/workbench");
  };

  const continueTrade = () => {
    if (!selectionDraft) return;
    transitionNavigate("/trade");
  };

  return (
    <AgentPageShell
      icon={FolderKanban}
      title="方案中心"
      description="选品推荐、四脑立项、贸易决策与经营沙盘统一归档，随时继续。"
    >
      <div className="entrance-reveal" style={{ animationDelay: "0.68s" }}>
        <Page3DScene className="mb-6" height={132} />
      </div>

      <div
        className="entrance-reveal grid grid-cols-1 gap-4"
        style={{ animationDelay: "0.76s" }}
      >
        <GlassCard
          title="联动链路"
          description="方案上下文通过浏览器本地持久化，在页面间自动携带"
          strong
        >
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <LinkMetric
              label="方案草稿"
              value={selectionDraft ? 1 : 0}
              actionLabel="去四脑立项"
              tone={selectionDraft ? "green" : "neutral"}
              onNavigate={() => transitionNavigate("/workbench")}
            />
            <LinkMetric
              label="关注组合"
              value={watchlist.length}
              actionLabel="去选品看板"
              tone={watchlist.length ? "green" : "neutral"}
              onNavigate={() => transitionNavigate("/dashboard")}
            />
            <LinkMetric
              label="方案沙盘"
              value={scenarios.length}
              actionLabel="去贸易决策"
              tone={scenarios.length ? "green" : "neutral"}
              onNavigate={() => transitionNavigate("/trade")}
            />
            <LinkMetric
              label="批量分析"
              value={batchRuns.length}
              actionLabel="去四脑工作台"
              tone={batchRuns.length ? "green" : "neutral"}
              onNavigate={() => transitionNavigate("/workbench")}
            />
          </div>
        </GlassCard>

        <GlassCard
          title="当前方案草稿"
          description="跨页面自动携带的选品与决策上下文"
          strong
        >
          {selectionDraft ? (
            <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1fr_auto]">
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
                <DraftMetric
                  label="方案"
                  value={selectionDraft.label || selectionDraft.keyword || "--"}
                />
                <DraftMetric label="品类" value={selectionDraft.category || "--"} />
                <DraftMetric label="市场" value={selectionDraft.market || "--"} />
                <DraftMetric
                  label="目标售价"
                  value={selectionDraft.price ? `$${selectionDraft.price}` : "--"}
                />
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {selectionDraft.isDemo && <DemoBadge />}
                <Button
                  variant="outline"
                  onClick={continueWorkbench}
                  disabled={!selectionDraft}
                >
                  <BrainCircuit className="h-4 w-4" />
                  四脑立项
                </Button>
                <Button
                  variant="outline"
                  onClick={continueTrade}
                  disabled={!selectionDraft}
                >
                  <Ship className="h-4 w-4" />
                  贸易决策
                </Button>
                <Button variant="ghost" onClick={() => setSelectionDraft(null)}>
                  清空
                </Button>
              </div>
            </div>
          ) : (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-slate-400">
                从选品看板或四脑工作台进入后会自动填充到这里。
              </p>
              <div className="flex flex-wrap items-center gap-2">
                <Button variant="outline" disabled>
                  <BrainCircuit className="h-4 w-4" />
                  四脑立项
                </Button>
                <Button variant="outline" disabled>
                  <Ship className="h-4 w-4" />
                  贸易决策
                </Button>
                {workflowOptions.length > 0 && (
                  <>
                    <Select
                      value={workflowOptions[0].value}
                      onValueChange={() => undefined}
                      options={workflowOptions}
                      className="w-56"
                      ariaLabel="选择全流程示例"
                    />
                    <Button onClick={applyWorkflowExample}>
                      <Wand2 className="h-4 w-4" />
                      一键示例方案
                    </Button>
                  </>
                )}
              </div>
            </div>
          )}
        </GlassCard>

        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <GlassCard
            title="关注清单"
            description="从推荐表收藏的组合"
            strong
            action={
              <Button
                size="sm"
                variant="outline"
                onClick={() => transitionNavigate("/dashboard")}
              >
                去选品看板
              </Button>
            }
          >
            {watchlist.length ? (
              <div className="grid grid-cols-1 gap-2">
                {watchlist.map((item) => (
                  <div
                    key={item.id}
                    className="glass-soft flex items-center justify-between gap-2 p-3"
                  >
                    <div className="min-w-0">
                      <p className="flex flex-wrap items-center gap-2 text-sm font-semibold text-white">
                        <Star className="h-3.5 w-3.5 fill-amber-300 text-amber-300" />
                        {item.label}
                        {item.isDemo && <DemoBadge />}
                      </p>
                      <p className="mt-0.5 text-[11px] text-slate-500">
                        {item.verdict ?? "--"} ·{" "}
                        {item.score != null ? `${item.score} 分` : "--"}
                      </p>
                    </div>
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={() => removeFromWatchlist(item.id)}
                      aria-label={`移除 ${item.label}`}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <Empty text="暂无关注组合" />
            )}
          </GlassCard>

          <GlassCard
            title="方案沙盘"
            description="贸易决策中保存的经营假设"
            strong
            action={
              <Button
                size="sm"
                variant="outline"
                onClick={() => transitionNavigate("/trade")}
              >
                去贸易决策
              </Button>
            }
          >
            {scenarios.length ? (
              <div className="grid grid-cols-1 gap-2">
                {scenarios.map((item) => (
                  <div
                    key={item.id}
                    className="glass-soft flex items-center justify-between gap-2 p-3"
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-sm font-semibold text-white">
                          {item.label}
                        </p>
                        {item.isDemo && <DemoBadge />}
                      </div>
                      <p className="mt-0.5 text-[11px] text-slate-500">
                        {item.quantity} 件 · 广告{" "}
                        {Math.round(item.ad_rate * 100)}% · 退货{" "}
                        {Math.round(item.return_rate * 100)}%
                      </p>
                    </div>
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={() => removeScenario(item.id)}
                      aria-label={`移除 ${item.label}`}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <Empty text="暂无已保存方案" />
            )}
          </GlassCard>
        </div>

        <GlassCard
          title="批量分析历史"
          description="最近 30 次四脑批量分析"
          strong
          action={
            <Button
              size="sm"
              variant="outline"
              onClick={() => transitionNavigate("/workbench")}
            >
              去四脑工作台
            </Button>
          }
        >
          {batchRuns.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>批次</TableHead>
                  <TableHead>方案数</TableHead>
                  <TableHead>创建时间</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {batchRuns.map((run) => (
                  <TableRow key={run.id}>
                    <TableCell className="flex items-center gap-2 font-semibold text-white">
                      <Layers className="h-3.5 w-3.5 text-accent" />
                      {run.label}
                      {run.isDemo && <DemoBadge />}
                    </TableCell>
                    <TableCell className="tabular">{run.items.length}</TableCell>
                    <TableCell className="font-mono text-xs">
                      {run.createdAt}
                    </TableCell>
                    <TableCell>
                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={() => removeBatchRun(run.id)}
                        aria-label={`删除 ${run.label}`}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <Empty text="暂无批量分析记录" />
          )}
        </GlassCard>

        {IS_OFFLINE ? <OfflineIntegrationPanel /> : <IntegrationPanel />}
      </div>
    </AgentPageShell>
  );
}

function DraftMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="glass-inset p-3">
      <p className="text-[11px] font-semibold text-slate-500">{label}</p>
      <p className="mt-0.5 truncate text-sm font-bold text-accent">{value}</p>
    </div>
  );
}

function LinkMetric({
  label,
  value,
  actionLabel,
  tone,
  onNavigate,
}: {
  label: string;
  value: number;
  actionLabel: string;
  tone: StatusTone;
  onNavigate: () => void;
}) {
  return (
    <div className="glass-inset p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] font-semibold text-slate-500">{label}</p>
        <Badge tone={tone} className="tabular">
          {value}
        </Badge>
      </div>
      <Button
        size="sm"
        variant="outline"
        className="mt-3 w-full"
        onClick={onNavigate}
      >
        <ArrowRight className="h-3.5 w-3.5" />
        {actionLabel}
      </Button>
    </div>
  );
}

function DemoBadge() {
  return <Badge tone="amber">演示预置</Badge>;
}

function Empty({ text }: { text: string }) {
  return (
    <div className="flex min-h-24 items-center justify-center text-sm text-slate-500">
      {text}
    </div>
  );
}
