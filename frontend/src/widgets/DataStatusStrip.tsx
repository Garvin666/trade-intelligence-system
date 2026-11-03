import { CheckCircle2, Cloud, FileText, Landmark, RefreshCw, ShieldCheck } from "lucide-react";
import type { DataStatus } from "@/shared/api/types";
import { Badge } from "@/shared/ui/badge";

interface DataStatusStripProps {
  status?: DataStatus;
}

export function DataStatusStrip({ status }: DataStatusStripProps) {
  const items = [
    { label: "联网快照", icon: Cloud, tone: ok(status?.online?.status) },
    { label: "Google Trends", icon: RefreshCw, tone: ok(status?.trends?.status) },
    { label: "平台榜单", icon: CheckCircle2, tone: ok(status?.platform_rankings?.status) },
    { label: "政策雷达", icon: Landmark, tone: ok(status?.policy?.status) },
    { label: "市场日报", icon: FileText, tone: ok(status?.market_daily?.enabled) },
    { label: "证据闸", icon: ShieldCheck, tone: ok(status?.crawl_quality?.decision_data_ready) },
  ];

  return (
    <div className="scrollbar-thin flex gap-2 overflow-x-auto pb-1">
      {items.map((item) => (
        <Badge
          key={item.label}
          tone={item.tone ? "green" : "neutral"}
          className="status-badge"
        >
          <span className="status-dot" aria-hidden />
          <item.icon className="h-3.5 w-3.5" />
          {item.label}
        </Badge>
      ))}
      {status?.as_of_label && (
        <Badge tone="cyan" className="status-badge ml-auto shrink-0">
          <span className="status-dot" aria-hidden />
          {status.as_of_label}
        </Badge>
      )}
    </div>
  );
}

function ok(value: unknown): boolean {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") {
    return ["ok", "ready", "enabled", "true"].includes(value.toLowerCase());
  }
  return false;
}
