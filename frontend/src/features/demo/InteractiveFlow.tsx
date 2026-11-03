import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import { Move, MousePointerClick } from "lucide-react";
import type { DashboardData } from "@/shared/api/types";
import { cn } from "@/shared/lib/utils";
import { Badge } from "@/shared/ui/badge";
import { DEMO_STAGES } from "./DEMO_STAGES";

interface InteractiveFlowProps {
  data?: DashboardData;
  activeStageId?: string;
  onStageChange?: (id: string) => void;
}

interface Point {
  x: number;
  y: number;
}

export function InteractiveFlow({
  data,
  activeStageId,
  onStageChange,
}: InteractiveFlowProps) {
  const controlled = activeStageId !== undefined;
  const [internalSelectedId, setInternalSelectedId] = useState(
    DEMO_STAGES[0].id,
  );
  const selectedId = controlled
    ? activeStageId
    : internalSelectedId;
  const [positions, setPositions] = useState<Record<string, Point>>({});
  const [lines, setLines] = useState<
    Array<{ x1: number; y1: number; x2: number; y2: number }>
  >([]);
  const containerRef = useRef<HTMLDivElement>(null);
  const nodeRefs = useRef(new Map<string, HTMLButtonElement>());
  const dragRef = useRef<{
    id: string;
    startX: number;
    startY: number;
    base: Point;
    moved: boolean;
  } | null>(null);

  const selected =
    DEMO_STAGES.find((stage) => stage.id === selectedId) ?? DEMO_STAGES[0];

  const selectStage = (id: string) => {
    if (controlled && onStageChange) {
      onStageChange(id);
    } else {
      setInternalSelectedId(id);
    }
  };

  const recomputeLines = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;
    const rect = container.getBoundingClientRect();
    const nextLines: Array<{
      x1: number;
      y1: number;
      x2: number;
      y2: number;
    }> = [];
    DEMO_STAGES.forEach((stage, index) => {
      const current = nodeRefs.current.get(stage.id);
      const next = nodeRefs.current.get(DEMO_STAGES[index + 1]?.id ?? "");
      if (!current || !next) return;
      const a = current.getBoundingClientRect();
      const b = next.getBoundingClientRect();
      nextLines.push({
        x1: a.left + a.width / 2 - rect.left,
        y1: a.top + a.height / 2 - rect.top,
        x2: b.left + b.width / 2 - rect.left,
        y2: b.top + b.height / 2 - rect.top,
      });
    });
    setLines(nextLines);
  }, []);

  useEffect(() => {
    recomputeLines();
    const observer = new ResizeObserver(recomputeLines);
    if (containerRef.current) observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [recomputeLines, positions, selectedId]);

  const onPointerDown = (
    event: ReactPointerEvent<HTMLButtonElement>,
    id: string,
  ) => {
    selectStage(id);
    if (window.innerWidth < 768) return;
    const button = event.currentTarget;
    button.setPointerCapture(event.pointerId);
    dragRef.current = {
      id,
      startX: event.clientX,
      startY: event.clientY,
      base: positions[id] ?? { x: 0, y: 0 },
      moved: false,
    };
  };

  const onPointerMove = (event: ReactPointerEvent<HTMLButtonElement>) => {
    const drag = dragRef.current;
    if (!drag) return;
    const dx = event.clientX - drag.startX;
    const dy = event.clientY - drag.startY;
    if (Math.abs(dx) + Math.abs(dy) > 5) drag.moved = true;
    setPositions((prev) => ({
      ...prev,
      [drag.id]: { x: drag.base.x + dx, y: drag.base.y + dy },
    }));
  };

  const onPointerUp = (event: ReactPointerEvent<HTMLButtonElement>) => {
    const drag = dragRef.current;
    if (!drag) return;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    if (!drag.moved) selectStage(drag.id);
    dragRef.current = null;
  };

  const summary = useMemo(() => {
    if (!data) return null;
    return {
      recommendations: data.recommendations?.length ?? 0,
      history: data.history?.length ?? 0,
      forecast: data.forecast?.length ?? 0,
    };
  }, [data]);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-bold text-white">交互式流程图</h2>
          <p className="mt-1 text-xs text-slate-400">点击查看详情，桌面端可拖拽节点</p>
        </div>
        <div className="hidden items-center gap-1.5 text-[11px] text-slate-500 xl:flex">
          <Move className="h-3.5 w-3.5" />
          拖拽
          <MousePointerClick className="h-3.5 w-3.5" />
          点击
        </div>
      </div>

      <div ref={containerRef} className="relative">
        <svg className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden="true">
          {lines.map((line, index) => (
            <line
              key={index}
              x1={line.x1}
              y1={line.y1}
              x2={line.x2}
              y2={line.y2}
              stroke="rgba(34,211,238,.28)"
              strokeWidth="1.5"
              strokeDasharray="4 4"
            />
          ))}
        </svg>
        <div className="grid grid-cols-2 gap-2">
          {DEMO_STAGES.map((stage, index) => {
            const active = stage.id === selectedId;
            const position = positions[stage.id] ?? { x: 0, y: 0 };
            return (
              <button
                key={stage.id}
                ref={(node) => {
                  if (node) nodeRefs.current.set(stage.id, node);
                  else nodeRefs.current.delete(stage.id);
                }}
                type="button"
                onPointerDown={(event) => onPointerDown(event, stage.id)}
                onPointerMove={onPointerMove}
                onPointerUp={onPointerUp}
                onClick={() => selectStage(stage.id)}
                className={cn(
                  "focus-ring relative touch-manipulation rounded-xl border p-3 text-left transition-all duration-200 active:scale-[.98]",
                  active
                    ? "border-cyan-300/40 bg-cyan-400/15 shadow-[0_10px_28px_-14px_rgba(34,211,238,.6)]"
                    : "glass-soft hover:bg-white/[.07]",
                )}
                style={{ transform: `translate(${position.x}px, ${position.y}px)` }}
              >
                <span className="font-mono text-[10px] text-slate-500">0{index + 1}</span>
                <stage.icon
                  className={cn(
                    "mt-1 h-4 w-4",
                    active ? "text-accent" : "text-slate-400",
                  )}
                />
                <span className="mt-1 block text-xs font-bold text-white">{stage.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="glass-inset mt-4 p-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="cyan">{selected.label}</Badge>
          {summary && <Badge tone="neutral">{summary.history} 条历史</Badge>}
        </div>
        <p className="mt-2 text-xs leading-5 text-slate-300">{selected.description}</p>
        <p className="tabular mt-2 font-mono text-[11px] text-amber-200">{selected.metric}</p>
      </div>
    </div>
  );
}
