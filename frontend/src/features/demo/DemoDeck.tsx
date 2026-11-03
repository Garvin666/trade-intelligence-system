import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from "react";
import { ChevronLeft, ChevronRight, LayoutGrid, Pause, Play } from "lucide-react";
import { gsap } from "gsap";
import { cn } from "@/shared/lib/utils";
import { usePrefersReducedMotion } from "@/shared/hooks/usePrefersReducedMotion";
import type { TransitionMode } from "@/shared/store/trade-intel";
import { Button } from "@/shared/ui/button";

export interface DemoSlide {
  id: string;
  label: string;
  node: ReactNode;
}

interface DemoDeckProps {
  slides: DemoSlide[];
  activeIndex: number;
  onIndexChange: (index: number) => void;
  mode: TransitionMode;
  playing: boolean;
  onTogglePlaying: () => void;
  onShowAll: () => void;
}

export function DemoDeck({
  slides,
  activeIndex,
  onIndexChange,
  mode,
  playing,
  onTogglePlaying,
  onShowAll,
}: DemoDeckProps) {
  const reduced = usePrefersReducedMotion();
  const effectiveMode = mode === "book" ? "cube" : mode;
  const stageRef = useRef<HTMLDivElement>(null);
  const enteringRef = useRef<HTMLDivElement>(null);
  const leavingRef = useRef<HTMLDivElement>(null);
  const timelineRef = useRef<gsap.core.Timeline | null>(null);
  const prevIndexRef = useRef(activeIndex);
  const directionRef = useRef<1 | -1>(1);
  const lastWheelRef = useRef(0);
  const [leaving, setLeaving] = useState<ReactNode | null>(null);
  const [hoverPaused, setHoverPaused] = useState(false);

  const requestChange = useCallback(
    (nextIndex: number) => {
      const count = slides.length;
      if (count <= 1) return;
      const normalized = ((nextIndex % count) + count) % count;
      if (normalized === activeIndex) return;
      prevIndexRef.current = activeIndex;
      directionRef.current = normalized > activeIndex ? 1 : -1;
      setLeaving(slides[activeIndex].node);
      onIndexChange(normalized);
    },
    [activeIndex, onIndexChange, slides],
  );

  useEffect(() => {
    if (!playing || reduced || hoverPaused || slides.length <= 1) return;
    const timer = window.setInterval(() => {
      requestChange(activeIndex + 1);
    }, 5200);
    return () => window.clearInterval(timer);
  }, [
    activeIndex,
    hoverPaused,
    playing,
    reduced,
    requestChange,
    slides.length,
  ]);

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    const onWheel = (event: WheelEvent) => {
      const deckEvent = event as WheelEvent & {
        __tradeDeckWheel?: boolean;
        __tradeDeckConsumed?: boolean;
      };
      deckEvent.__tradeDeckWheel = true;
      const now = Date.now();
      if (now - lastWheelRef.current < 900) {
        event.stopPropagation();
        event.preventDefault();
        return;
      }
      const deltaY = Math.abs(event.deltaY);
      const deltaX = Math.abs(event.deltaX);
      const delta = deltaY >= deltaX ? event.deltaY : event.deltaX;
      if (Math.abs(delta) < 24) return;
      const next =
        delta > 0
          ? activeIndex < slides.length - 1
            ? activeIndex + 1
            : null
          : activeIndex > 0
            ? activeIndex - 1
            : null;
      if (next !== null) {
        lastWheelRef.current = now;
        deckEvent.__tradeDeckConsumed = true;
        requestChange(next);
        event.stopPropagation();
      }
      event.preventDefault();
    };
    stage.addEventListener("wheel", onWheel, { passive: false });
    return () => stage.removeEventListener("wheel", onWheel);
  }, [activeIndex, requestChange, slides.length]);

  useLayoutEffect(() => {
    if (prevIndexRef.current === activeIndex) return;
    prevIndexRef.current = activeIndex;
    const entering = enteringRef.current;
    if (!entering) return;
    const leavingEl = leavingRef.current;
    const dir = directionRef.current;

    timelineRef.current?.kill();
    const tl = gsap.timeline({
      defaults: { ease: "power2.inOut" },
      onComplete: () => setLeaving(null),
    });
    timelineRef.current = tl;

    if (leavingEl) {
      if (effectiveMode === "cube") {
        tl.to(leavingEl, {
          rotationY: dir * -34,
          xPercent: dir * 8,
          autoAlpha: 0,
          duration: 0.3,
        });
      } else {
        tl.to(leavingEl, {
          xPercent: dir * 24,
          yPercent: effectiveMode === "slide-y" ? dir * 24 : 0,
          autoAlpha: 0,
          duration: 0.3,
        });
      }
    }

    if (effectiveMode === "cube") {
      gsap.set(entering, {
        transformPerspective: 1100,
        rotationY: dir * 55,
        xPercent: dir * 12,
        autoAlpha: 0,
      });
      tl.to(
        entering,
        {
          rotationY: 0,
          xPercent: 0,
          autoAlpha: 1,
          duration: 0.46,
        },
        "<",
      );
    } else {
      gsap.set(entering, {
        xPercent: -dir * 20,
        yPercent: effectiveMode === "slide-y" ? -dir * 20 : 0,
        autoAlpha: 0,
      });
      tl.to(
        entering,
        {
          xPercent: 0,
          yPercent: 0,
          autoAlpha: 1,
          duration: 0.46,
        },
        "<",
      );
    }
  }, [activeIndex, effectiveMode, mode]);

  useEffect(
    () => () => {
      timelineRef.current?.kill();
    },
    [],
  );

  const handleKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    event.stopPropagation();
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      event.preventDefault();
      requestChange(activeIndex + 1);
    } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      event.preventDefault();
      requestChange(activeIndex - 1);
    }
  };

  return (
    <div data-demo-deck>
      <div
        data-demo-deck-controls
        className="mb-3 flex flex-wrap items-center justify-between gap-3"
      >
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => requestChange(activeIndex - 1)}
            disabled={activeIndex === 0}
            aria-label="上一页"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => requestChange(activeIndex + 1)}
            disabled={activeIndex === slides.length - 1}
            aria-label="下一页"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="glass-inset flex items-center gap-1 rounded-lg p-1" role="group" aria-label="演示页">
            {slides.map((slide, index) => (
              <button
                key={slide.id}
                type="button"
                onClick={() => requestChange(index)}
                className={cn(
                  "focus-ring h-2.5 w-2.5 rounded-full transition-all duration-300",
                  index === activeIndex
                    ? "w-6 bg-cyan-300"
                    : "bg-white/20 hover:bg-white/40",
                )}
                aria-label={`切换到 ${slide.label}`}
                aria-pressed={index === activeIndex}
              />
            ))}
          </div>
          <span className="tabular font-mono text-[11px] text-slate-500">
            {activeIndex + 1} / {slides.length}
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={onTogglePlaying}
            aria-label={playing ? "暂停自动播放" : "自动播放"}
            aria-pressed={playing}
          >
            {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={onShowAll}
            aria-label="全部展示"
            title="全部展示"
          >
            <LayoutGrid className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div
        ref={stageRef}
        tabIndex={0}
        role="region"
        aria-label="演示播片"
        onKeyDown={handleKeyDown}
        onMouseEnter={() => setHoverPaused(true)}
        onMouseLeave={() => setHoverPaused(false)}
        onFocus={() => setHoverPaused(true)}
        onBlur={() => setHoverPaused(false)}
        className="focus-ring deck-viewport relative overflow-hidden rounded-xl outline-none"
      >
        {leaving && (
          <div
            ref={leavingRef}
            className="deck-slide pointer-events-none absolute inset-0 z-10"
            aria-hidden="true"
          >
            {leaving}
          </div>
        )}
        <div
          ref={enteringRef}
          className="deck-slide relative z-20"
        >
          {slides[activeIndex]?.node}
        </div>
      </div>
    </div>
  );
}
