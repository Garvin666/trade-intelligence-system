import { cn } from "@/shared/lib/utils";
import { LogoMark } from "@/shared/brand/LogoMark";

export interface RouteStatusItem {
  label: string;
  value: string;
  tone?: "cyan" | "amber" | "green" | "violet";
}

interface RouteStatusBarProps {
  items: RouteStatusItem[];
  className?: string;
}

const toneText: Record<NonNullable<RouteStatusItem["tone"]>, string> = {
  cyan: "text-cyan-300",
  amber: "text-amber-300",
  green: "text-emerald-300",
  violet: "text-violet-300",
};

const toneDot: Record<NonNullable<RouteStatusItem["tone"]>, string> = {
  cyan: "bg-cyan-400",
  amber: "bg-amber-400",
  green: "bg-emerald-400",
  violet: "bg-violet-400",
};

/**
 * 静态“清关状态条”：暖墨底 + 朱红签注线 + 4 个状态格 + 1px 分隔线。
 * 全条仅保留数据状态点脉冲一处循环动效，其余均为静态呈现。
 */
export function RouteStatusBar({ items, className }: RouteStatusBarProps) {
  return (
    <section
      aria-label="系统状态条"
      className={cn(
        "route-status-bar relative flex min-h-20 items-stretch overflow-hidden rounded-lg border border-white/10 bg-raised",
        className,
      )}
    >
      <div className="relative z-10 hidden shrink-0 items-center gap-3 border-r border-white/8 px-5 lg:flex">
        <LogoMark size={34} />
        <div className="leading-tight">
          <p className="text-sm font-extrabold text-white">远帆智品</p>
          <p className="font-mono text-[10px] tracking-[.16em] text-slate-400 uppercase">
            Trade Intelligence
          </p>
        </div>
      </div>

      <div className="relative z-10 grid min-w-0 flex-1 grid-cols-2 divide-x divide-white/8 sm:grid-cols-4">
        {items.map((item, index) => (
          <div
            key={item.label}
            className="flex min-w-0 flex-col justify-center gap-1 px-4 py-3"
          >
            <span
              className={cn(
                "flex items-center gap-1.5 text-[11px] font-semibold tracking-[.08em] text-slate-400 uppercase",
              )}
            >
              <span
                className={cn(
                  "route-status-dot h-1.5 w-1.5 shrink-0 rounded-full",
                  toneDot[item.tone ?? "cyan"],
                )}
                aria-hidden
              />
              {item.label}
            </span>
            <span
              className={cn(
                "tabular truncate text-[13px] font-bold",
                toneText[item.tone ?? "cyan"],
                index === items.length - 1 ? "text-white" : "",
              )}
            >
              {item.value}
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
