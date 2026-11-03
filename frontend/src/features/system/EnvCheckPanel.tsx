import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  MinusCircle,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { useEnvCheck } from "@/shared/api/hooks";
import { IS_OFFLINE } from "@/shared/api/offline";
import type { EnvCheckItem, EnvCheckStatus } from "@/shared/api/types";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { GlassCard } from "@/shared/ui/glass-card";

const STATUS_META: Record<
  EnvCheckStatus,
  { icon: typeof CheckCircle2; tone: "green" | "amber" | "red" | "neutral"; label: string }
> = {
  ok: { icon: CheckCircle2, tone: "green", label: "通过" },
  warn: { icon: AlertTriangle, tone: "amber", label: "警告" },
  fail: { icon: XCircle, tone: "red", label: "失败" },
  skip: { icon: MinusCircle, tone: "neutral", label: "跳过" },
};

export function EnvCheckPanel() {
  const { data, isLoading, isError, refetch, isFetching } = useEnvCheck();

  if (IS_OFFLINE) {
    return (
      <GlassCard>
        <p className="text-sm text-slate-400">
          环境自检需要在线后端执行检查，离线单文件模式不可用。
        </p>
      </GlassCard>
    );
  }

  if (isLoading && !data) {
    return (
      <GlassCard>
        <div className="flex items-center gap-3">
          <Loader2 className="h-5 w-5 shrink-0 animate-spin text-accent" />
          <div>
            <p className="text-sm font-semibold text-white">正在运行环境自检…</p>
            <p className="mt-0.5 text-xs text-slate-400">
              快速检查通常需要数秒；首次进入时后端可能正在执行并发探测，请稍候。
            </p>
          </div>
        </div>
        <div className="mt-4 grid gap-2">
          {[0, 1, 2].map((item) => (
            <div key={item} className="glass-inset h-10 animate-pulse" />
          ))}
        </div>
      </GlassCard>
    );
  }

  if (isError || !data) {
    return (
      <GlassCard>
        <p className="text-sm text-red-300">环境自检请求失败，请确认后端已启动。</p>
      </GlassCard>
    );
  }

  const summary = data.summary ?? { ok: 0, warn: 0, fail: 0, skip: 0 };
  const groups = Object.entries(data.groups ?? {});
  const overallTone = data.overall === "ok" ? "green" : "red";

  return (
    <div className="grid gap-4">
      <GlassCard
        title="环境自检"
        description={`${data.python ?? "--"} · 后端 ${data.base_url ?? "--"} · 深度 ${data.depth ?? "quick"}`}
        action={
          <Button
            size="sm"
            variant="outline"
            disabled={isFetching}
            onClick={() => void refetch()}
          >
            {isFetching ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            {isFetching ? "检查中..." : "重新检查"}
          </Button>
        }
      >
        <div className="flex flex-wrap items-center gap-3">
          <Badge tone={overallTone}>
            <ShieldCheck className="h-3.5 w-3.5" />
            {data.overall === "ok" ? "总体通过" : "未通过"}
          </Badge>
          <span className="text-xs text-slate-400">
            ok={summary.ok} warn={summary.warn} fail={summary.fail} skip={summary.skip} ·{" "}
            {formatTime(data.generated_at)}
          </span>
        </div>

        {groups.length === 0 && (
          <p className="mt-4 text-sm text-slate-400">没有可展示的检查分组。</p>
        )}
      </GlassCard>

      {groups.map(([name, group]) => (
        <GlassCard key={name} title={group.label} description={name}>
          <div className="grid gap-2.5">
            {group.results.map((item) => (
              <CheckRow key={item.id} item={item} />
            ))}
          </div>
        </GlassCard>
      ))}
    </div>
  );
}

function CheckRow({ item }: { item: EnvCheckItem }) {
  const meta = STATUS_META[item.status] ?? STATUS_META.skip;
  const Icon = meta.icon;
  return (
    <div className="glass-inset flex items-start gap-3 p-3">
      <Icon
        className={
          "mt-0.5 h-4 w-4 shrink-0 " +
          (item.status === "ok"
            ? "text-emerald-300"
            : item.status === "warn"
              ? "text-amber-300"
              : item.status === "fail"
                ? "text-red-300"
                : "text-slate-500")
        }
      />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-slate-200">{item.label}</span>
          <Badge tone={meta.tone}>{meta.label}</Badge>
          <span className="font-mono text-[10px] text-slate-600">{item.duration_ms}ms</span>
        </div>
        {item.detail && (
          <p className="mt-1 break-words text-xs leading-relaxed text-slate-400">{item.detail}</p>
        )}
      </div>
    </div>
  );
}

function formatTime(value?: string): string {
  if (!value) return "--";
  return value.replace("T", " ").slice(0, 19);
}
