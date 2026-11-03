import { Pause, Play, Repeat, RotateCcw } from "lucide-react";
import { cn } from "@/shared/lib/utils";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { DEMO_STAGES } from "./DEMO_STAGES";
import { useDemoPlayback } from "./useDemoPlayback";

interface PipelinePlayerProps {
  autoStart?: boolean;
  activeStageId?: string;
  onStageChange?: (id: string) => void;
  playing?: boolean;
  onPlayToggle?: () => void;
}

export function PipelinePlayer({
  autoStart = false,
  activeStageId,
  onStageChange,
  playing,
  onPlayToggle,
}: PipelinePlayerProps) {
  const controlled = typeof playing === "boolean";
  const internal = useDemoPlayback({
    intervalMs: 1200,
    autoStart: controlled ? false : autoStart,
  });
  const resolvedPlaying = controlled ? playing : internal.playing;
  const resolvedIndex = activeStageId
    ? Math.max(
        0,
        DEMO_STAGES.findIndex((stage) => stage.id === activeStageId),
      )
    : internal.stageIndex;
  const active = DEMO_STAGES[resolvedIndex] ?? DEMO_STAGES[0];

  const handlePlayToggle = () => {
    if (controlled && onPlayToggle) {
      onPlayToggle();
      return;
    }
    if (resolvedPlaying) {
      internal.pause();
    } else {
      internal.play();
    }
  };

  const handleReset = () => {
    if (activeStageId && onStageChange) {
      onStageChange(DEMO_STAGES[0].id);
      return;
    }
    internal.reset();
  };

  return (
    <div className="glass-strong p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-white">可播放链路动画</h2>
          <p className="mt-1 text-xs text-slate-400">数据到决策的完整链路，自动推进并高亮当前阶段</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={handlePlayToggle}
            aria-label={resolvedPlaying ? "暂停" : "播放"}
          >
            {resolvedPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
            {resolvedPlaying ? "暂停" : "播放"}
          </Button>
          <Button variant="ghost" size="sm" onClick={handleReset} aria-label="重置">
            <RotateCcw className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={internal.setLoop}
            className={cn(internal.loop && "text-accent")}
            aria-pressed={internal.loop}
            aria-label="循环播放"
          >
            <Repeat className="h-4 w-4" />
            {internal.loop ? "循环" : "单次"}
          </Button>
        </div>
      </div>

      <div className="mt-5 flex items-center gap-1.5 overflow-x-auto pb-2">
        {DEMO_STAGES.map((stage, index) => {
          const isActive = index === resolvedIndex;
          const isDone = index < resolvedIndex;
          return (
            <div key={stage.id} className="flex min-w-0 flex-1 items-center gap-1.5">
              <button
                type="button"
                onClick={() => onStageChange?.(stage.id)}
                className={cn(
                  "focus-ring flex min-w-0 flex-1 cursor-pointer flex-col items-center gap-1 rounded-lg border px-2 py-2 text-center transition-all duration-300 active:scale-[.98]",
                  isActive
                    ? "border-cyan-300/40 bg-cyan-400/15 shadow-[0_8px_24px_-12px_rgba(34,211,238,.45)]"
                    : isDone
                      ? "border-white/10 bg-white/[.05] hover:bg-white/10"
                      : "border-white/[.06] bg-transparent hover:bg-white/[.06]",
                )}
                aria-pressed={isActive}
                aria-label={`切换到 ${stage.label}`}
              >
                <stage.icon
                  className={cn(
                    "h-4 w-4",
                    isActive ? "text-accent" : isDone ? "text-slate-300" : "text-slate-600",
                  )}
                />
                <span
                  className={cn(
                    "truncate text-[11px] font-semibold",
                    isActive ? "text-white" : isDone ? "text-slate-300" : "text-slate-600",
                  )}
                >
                  {stage.label}
                </span>
              </button>
              {index < DEMO_STAGES.length - 1 && (
                <div
                  className={cn(
                    "h-px w-2 shrink-0 sm:w-3",
                    isDone ? "bg-cyan-300/50" : "bg-white/10",
                  )}
                />
              )}
            </div>
          );
        })}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3 rounded-lg border border-white/10 bg-white/[.04] px-3 py-2.5">
        <Badge tone="cyan">当前阶段 · {active.label}</Badge>
        <p className="min-w-0 flex-1 truncate text-xs text-slate-300">{active.description}</p>
        <span className="tabular font-mono text-xs text-amber-200">{active.metric}</span>
      </div>
    </div>
  );
}
