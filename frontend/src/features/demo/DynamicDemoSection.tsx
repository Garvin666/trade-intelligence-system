import {
  Suspense,
  lazy,
  useMemo,
  useState,
} from "react";
import { ArrowLeft, LayoutGrid, MonitorPlay, Sparkles } from "lucide-react";
import { useCatalog, useDashboardData } from "@/shared/api/hooks";
import { IS_OFFLINE } from "@/shared/api/offline";
import { useTradeIntelStore } from "@/shared/store/trade-intel";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { GlassCard } from "@/shared/ui/glass-card";
import { Select, type SelectOption } from "@/shared/ui/select";
import { Skeleton } from "@/shared/ui/skeleton";
import { DEMO_STAGES } from "./DEMO_STAGES";
import { DemoDeck, type DemoSlide } from "./DemoDeck";
import { DemoSectionMotion } from "./DemoSectionMotion";
import { InteractiveFlow } from "./InteractiveFlow";
import { LiveMarketChart } from "./LiveMarketChart";
import { OperationGuideDiagram } from "./OperationGuideDiagram";
import { PipelinePlayer } from "./PipelinePlayer";

const PipelineScene3D = lazy(() =>
  import("./PipelineScene3D").then((module) => ({
    default: module.PipelineScene3D,
  })),
);

function toOptions(map: Record<string, string> | undefined): SelectOption[] {
  return Object.entries(map ?? {}).map(([value, label]) => ({ value, label }));
}

interface DynamicDemoSectionProps {
  hideDeckToggle?: boolean;
  onOpenDemoDeck?: () => void;
  onBack?: () => void;
}

export function DynamicDemoSection({
  hideDeckToggle = false,
  onOpenDemoDeck,
  onBack,
}: DynamicDemoSectionProps) {
  const [category, setCategory] = useState("cn_latiao");
  const [market, setMarket] = useState("us");
  const [viewMode, setViewMode] = useState<"deck" | "all">(
    hideDeckToggle ? "all" : "deck",
  );
  const [activeStageId, setActiveStageId] = useState(DEMO_STAGES[0].id);
  const [playing, setPlaying] = useState(
    () =>
      typeof window === "undefined" ||
      !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
  );
  const [speed, setSpeed] = useState(1);
  const [deckIndex, setDeckIndex] = useState(0);
  const transitionMode = useTradeIntelStore((state) => state.transitionMode);
  const { data: catalog } = useCatalog();
  const { data, isLoading, isError } = useDashboardData({ category, market });

  const scene = useMemo(
    () => (
      <Suspense fallback={<Skeleton className="h-[420px] w-full" />}>
        <PipelineScene3D
          activeStageId={activeStageId}
          onStageChange={setActiveStageId}
          playing={playing}
          onTogglePlaying={() => setPlaying((value) => !value)}
          speed={speed}
          onSpeedChange={setSpeed}
        />
      </Suspense>
    ),
    [activeStageId, playing, speed],
  );

  const slides = useMemo<DemoSlide[]>(
    () => [
      {
        id: "scene",
        label: "3D 系统流程",
        node: scene,
      },
      {
        id: "guide",
        label: "操作指引",
        node: <OperationGuideDiagram autoStart={playing} />,
      },
      {
        id: "pipeline",
        label: "管线播放",
        node: (
          <PipelinePlayer
            autoStart={playing}
            activeStageId={activeStageId}
            onStageChange={setActiveStageId}
            playing={playing}
            onPlayToggle={() => setPlaying((value) => !value)}
          />
        ),
      },
      {
        id: "chart",
        label: "实时图表",
        node: (
          <LiveMarketChart
            history={data?.history ?? []}
            forecast={data?.forecast ?? []}
            autoStart={playing}
          />
        ),
      },
      {
        id: "flow",
        label: "交互流程",
        node: (
          <InteractiveFlow
            data={data}
            activeStageId={activeStageId}
            onStageChange={setActiveStageId}
          />
        ),
      },
    ],
    [activeStageId, data, playing, scene],
  );

  const showDeck = !hideDeckToggle && viewMode === "deck";

  return (
    <section
      className="relative border-t border-white/10 bg-[#08111f]/60 py-14"
      aria-label="动态演示区"
    >
      <div className="mx-auto max-w-[1440px] px-4 sm:px-6">
        <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <MonitorPlay className="h-5 w-5 text-cyan-300" />
              <h2 className="text-lg font-bold text-white">动态演示区</h2>
            </div>
            <p className="mt-1 max-w-2xl text-sm text-slate-400">
              系统流程动画 + 操作指引 + 可播放链路 + 动态图表 + 交互式流程图
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {onBack && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onBack}
                aria-label="返回首页"
                title="返回首页"
              >
                <ArrowLeft className="h-4 w-4" />
                返回首页
              </Button>
            )}
            <div className="flex min-w-0 flex-col gap-1">
              <span className="text-[11px] font-semibold text-slate-500">演示品类</span>
              <Select
                value={category}
                onValueChange={setCategory}
                options={toOptions(catalog?.categories)}
                ariaLabel="演示品类"
                className="w-40"
              />
            </div>
            <div className="flex min-w-0 flex-col gap-1">
              <span className="text-[11px] font-semibold text-slate-500">演示市场</span>
              <Select
                value={market}
                onValueChange={setMarket}
                options={toOptions(catalog?.markets)}
                ariaLabel="演示市场"
                className="w-36"
              />
            </div>
            <div className="flex items-center gap-2">
              <Badge tone={IS_OFFLINE ? "amber" : "cyan"}>
                {IS_OFFLINE ? "离线快照" : "在线数据"}
              </Badge>
              <Badge tone="neutral">
                <Sparkles className="h-3.5 w-3.5" />
                自动播放
              </Badge>
            </div>
            {!hideDeckToggle && onOpenDemoDeck && (
              <Button
                variant="outline"
                size="sm"
                onClick={onOpenDemoDeck}
                aria-label="播片演示"
                title="播片演示"
              >
                <MonitorPlay className="h-4 w-4" />
                播片演示
              </Button>
            )}
            {!hideDeckToggle && (
              <Button
                variant={viewMode === "deck" ? "secondary" : "ghost"}
                size="sm"
                onClick={() =>
                  setViewMode((value) => (value === "deck" ? "all" : "deck"))
                }
                aria-label={viewMode === "deck" ? "全部展示" : "播片模式"}
                title={viewMode === "deck" ? "全部展示" : "播片模式"}
              >
                {viewMode === "deck" ? (
                  <LayoutGrid className="h-4 w-4" />
                ) : (
                  <MonitorPlay className="h-4 w-4" />
                )}
              </Button>
            )}
          </div>
        </header>

        {showDeck && (
          <DemoDeck
            slides={slides}
            activeIndex={deckIndex}
            onIndexChange={setDeckIndex}
            mode={transitionMode}
            playing={playing}
            onTogglePlaying={() => setPlaying((value) => !value)}
            onShowAll={() => setViewMode("all")}
          />
        )}

        {!showDeck && (
          <DemoSectionMotion>
          <div className="space-y-4">
            <div className="tilt-card demo-reveal">{scene}</div>
            <div className="tilt-card demo-reveal">
              <OperationGuideDiagram autoStart={playing} />
            </div>
            <div className="tilt-card demo-reveal">
              <PipelinePlayer
                autoStart={playing}
                activeStageId={activeStageId}
                onStageChange={setActiveStageId}
                playing={playing}
                onPlayToggle={() => setPlaying((value) => !value)}
              />
            </div>
            <div className="demo-reveal grid gap-4 xl:grid-cols-[1.65fr_1fr]">
              <GlassCard className="tilt-card p-5">
                {isLoading && !data ? (
                  <Skeleton className="h-[360px] w-full" />
                ) : (
                  <LiveMarketChart
                    history={data?.history ?? []}
                    forecast={data?.forecast ?? []}
                    autoStart={playing}
                  />
                )}
              </GlassCard>
              <GlassCard className="tilt-card p-5">
                <InteractiveFlow
                  data={data}
                  activeStageId={activeStageId}
                  onStageChange={setActiveStageId}
                />
              </GlassCard>
            </div>
          </div>
          </DemoSectionMotion>
        )}

        {isError && (
          <p className="mt-4 text-xs text-amber-200">
            演示数据加载失败，已显示离线/空态；请确认后端或快照可用。
          </p>
        )}
      </div>
    </section>
  );
}
