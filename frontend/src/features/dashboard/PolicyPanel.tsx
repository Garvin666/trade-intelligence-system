import { ExternalLink, Radio } from "lucide-react";
import type { PolicyEvent } from "@/shared/api/types";
import { cn } from "@/shared/lib/utils";
import { marketName } from "@/shared/lib/names";
import { Badge } from "@/shared/ui/badge";

const impactTone: Record<string, "red" | "amber" | "green" | "neutral"> = {
  high: "red",
  medium: "amber",
  low: "green",
};

export function PolicyPanel({ events }: { events: PolicyEvent[] }) {
  return (
    <div className="grid gap-2">
      {events.slice(0, 6).map((event) => (
        <article
          key={event.code}
          className="glass-soft flex flex-col gap-2 p-3.5 sm:flex-row sm:items-start sm:justify-between"
        >
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={impactTone[event.impact_level] ?? "neutral"}>
                {event.impact_level === "high" ? "高" : event.impact_level === "medium" ? "中" : "低"}
              </Badge>
              <Badge tone="cyan">{marketName(event.market)}</Badge>
              <span className="font-mono text-[10px] text-slate-500">{event.effective_date}</span>
            </div>
            <h3 className="mt-2 text-sm font-bold text-white">{event.title}</h3>
            <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-400">{event.description}</p>
          </div>
          <div className="flex shrink-0 items-center gap-2 text-[11px] text-slate-500">
            <Radio className="h-3.5 w-3.5 text-emerald-300" />
            <span className={cn(event.verified ? "text-emerald-300" : "text-amber-300")}>
              {event.verified ? "官方已核验" : "待核实"}
            </span>
            {event.url && (
              <a
                href={event.url}
                target="_blank"
                rel="noreferrer"
                className="focus-ring rounded p-1 text-slate-400 hover:text-accent"
                aria-label="打开政策原文"
              >
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            )}
          </div>
        </article>
      ))}
    </div>
  );
}
