import { useEffect, useState } from "react";
import {
  BrainCircuit,
  FileDown,
  LayoutDashboard,
  MousePointerClick,
  Pause,
  Play,
  RotateCcw,
  Ship,
  SlidersHorizontal,
} from "lucide-react";
import { cn } from "@/shared/lib/utils";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";

export interface GuideStep {
  id: string;
  label: string;
  description: string;
  icon: typeof SlidersHorizontal;
}

export const GUIDE_STEPS: GuideStep[] = [
  {
    id: "select",
    label: "选择组合",
    description: "先选择商品品类与目标市场，系统会按该组合加载数据。",
    icon: SlidersHorizontal,
  },
  {
    id: "dashboard",
    label: "查看看板",
    description: "查看趋势、预测、Top 推荐与政策雷达，快速判断机会。",
    icon: LayoutDashboard,
  },
  {
    id: "four-brain",
    label: "四脑分析",
    description: "进入四脑工作台，用市场、产品、风险、增长四个角色深入分析。",
    icon: BrainCircuit,
  },
  {
    id: "trade",
    label: "贸易决策",
    description: "输入成本与售价，生成关税、物流、合规与利润结论。",
    icon: Ship,
  },
  {
    id: "export",
    label: "导出报告",
    description: "将当前选品结论导出为 Markdown 或 PDF，方便汇报与存档。",
    icon: FileDown,
  },
];

interface OperationGuideDiagramProps {
  autoStart?: boolean;
}

export function OperationGuideDiagram({
  autoStart = false,
}: OperationGuideDiagramProps) {
  const [active, setActive] = useState(0);
  const [playing, setPlaying] = useState(autoStart);

  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => {
      setActive((value) => (value + 1) % GUIDE_STEPS.length);
    }, 1600);
    return () => window.clearInterval(timer);
  }, [playing]);

  const step = GUIDE_STEPS[active];
  const progress = (active / (GUIDE_STEPS.length - 1)) * 100;
  const cursorLeft = 5 + progress * 0.9;

  return (
    <div className="glass-strong p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-white">系统操作指引</h2>
          <p className="mt-1 text-xs text-slate-400">跟随光标按顺序操作，快速上手本系统</p>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone="cyan">5 步上手</Badge>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setPlaying((value) => !value)}
            aria-label={playing ? "暂停指引" : "播放指引"}
          >
            {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setActive(0);
              setPlaying(false);
            }}
            aria-label="重置指引"
          >
            <RotateCcw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div className="relative mt-6 h-8">
        <div className="absolute left-[5%] right-[5%] top-3.5 h-0.5 bg-white/10" />
        <div
          className="absolute top-3.5 h-0.5 bg-gradient-to-r from-cyan-400 to-amber-400 transition-all duration-500"
          style={{ left: "5%", width: `${progress * 0.9}%` }}
        />
        <div
          className="absolute top-1 -translate-x-1/2 transition-all duration-500"
          style={{ left: `${cursorLeft}%` }}
          aria-hidden="true"
        >
          <MousePointerClick className="h-5 w-5 text-amber-300 drop-shadow-[0_2px_8px_rgba(245,158,11,.55)]" />
        </div>
      </div>

      <div className="mt-2 grid grid-cols-2 gap-2 md:grid-cols-5">
        {GUIDE_STEPS.map((item, index) => {
          const isActive = index === active;
          const isDone = index < active;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => {
                setActive(index);
                setPlaying(false);
              }}
              className={cn(
                "focus-ring flex min-h-[96px] flex-col gap-1.5 rounded-xl border p-3 text-left transition-all duration-300 active:scale-[.98]",
                isActive
                  ? "border-cyan-300/40 bg-cyan-400/15 shadow-[0_10px_30px_-14px_rgba(34,211,238,.65)]"
                  : isDone
                    ? "glass-soft border-white/10 bg-white/[.05]"
                    : "glass-soft border-white/[.07]",
              )}
              aria-pressed={isActive}
            >
              <span className="flex items-center justify-between">
                <item.icon
                  className={cn(
                    "h-4 w-4",
                    isActive ? "text-accent" : "text-slate-400",
                  )}
                />
                <span
                  className={cn(
                    "font-mono text-[10px]",
                    isActive ? "text-accent" : "text-slate-600",
                  )}
                >
                  0{index + 1}
                </span>
              </span>
              <span className="text-xs font-bold text-white">{item.label}</span>
              <span className="line-clamp-2 text-[10px] leading-4 text-slate-500">
                {item.description}
              </span>
            </button>
          );
        })}
      </div>

      <div className="glass-inset mt-4 flex flex-wrap items-center gap-3 p-3">
        <Badge tone="amber">当前操作 · {step.label}</Badge>
        <p className="min-w-0 flex-1 text-xs leading-5 text-slate-300">{step.description}</p>
        <span className="font-mono text-[10px] text-slate-500">
          {active + 1} / {GUIDE_STEPS.length}
        </span>
      </div>
    </div>
  );
}
