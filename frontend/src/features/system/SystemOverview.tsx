import {
  Boxes,
  FlaskConical,
  HeartPulse,
  Landmark,
  ServerCog,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import { useRefreshPolicy, useSystemStatus } from "@/shared/api/hooks";
import { IS_OFFLINE } from "@/shared/api/offline";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { GlassCard } from "@/shared/ui/glass-card";
import { Skeleton } from "@/shared/ui/skeleton";

export function SystemOverview() {
  const { data, isLoading, isError } = useSystemStatus();
  const refreshPolicy = useRefreshPolicy();

  if (IS_OFFLINE) {
    return <OfflineNotice />;
  }

  if (isLoading && !data) {
    return (
      <div className="grid gap-4">
        {[0, 1, 2].map((item) => (
          <GlassCard key={item} className="p-5">
            <Skeleton className="h-20" />
            <p className="mt-3 text-sm text-slate-400">正在加载系统状态…</p>
          </GlassCard>
        ))}
      </div>
    );
  }

  if (isError || !data) {
    return (
      <GlassCard>
        <p className="text-sm text-red-300">系统状态加载失败，请确认后端已启动。</p>
      </GlassCard>
    );
  }

  const { health, engineering, systemEval, suppliers } = data;
  const jobs = health?.jobs?.items ?? [];
  const running = jobs.filter((job) => job.status === "running").length;
  const supplierRows = suppliers?.rows ?? [];
  const gate = systemEval?.gate as
    | { passed?: boolean; failed_metrics?: string[] }
    | undefined;
  const gateFailed = gate && !gate.passed ? (gate.failed_metrics ?? []) : [];

  return (
    <div className="grid gap-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric
          icon={HeartPulse}
          label="后端服务"
          value={health?.status ?? "--"}
          tone={health?.status === "ok" ? "green" : "red"}
        />
        <Metric
          icon={ServerCog}
          label="后台任务"
          value={`${running} 运行 / ${jobs.length} 个`}
          tone={running > 0 ? "amber" : "cyan"}
        />
        <Metric
          icon={FlaskConical}
          label="自动化测试"
          value={
            engineering?.test_count
              ? `${engineering.test_passed ?? "--"} / ${engineering.test_count} 通过`
              : "--"
          }
          tone="cyan"
        />
        <Metric
          icon={Boxes}
          label="供应商快照"
          value={`${supplierRows.length} 行`}
          tone={supplierRows.length ? "green" : "neutral"}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <GlassCard title="服务与接口" description="健康检查、MCP 与数据文件状态">
          <div className="grid gap-2 text-sm">
            <InfoRow label="MCP Server" value={health?.mcp ? "已挂载" : "未挂载"} />
            <InfoRow label="数据文件" value={formatFiles(health?.data_files)} />
            <InfoRow label="数据更新至" value={health?.data_status?.as_of_label ?? "--"} />
          </div>
        </GlassCard>

        <GlassCard
          title="政策雷达"
          description="官方源近实时刷新"
          action={
            <Button
              size="sm"
              variant="outline"
              disabled={refreshPolicy.isPending}
              onClick={() => refreshPolicy.mutate({})}
            >
              <Landmark className="h-4 w-4" />
              {refreshPolicy.isPending ? "刷新中..." : "立即刷新"}
            </Button>
          }
        >
          {refreshPolicy.isSuccess && (
            <p className="mb-2 text-xs text-emerald-300">
              已刷新：{refreshPolicy.data?.updated_at ?? "--"}，核实 {refreshPolicy.data?.verified_count ?? 0} 条
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <Badge tone={health?.data_status?.policy?.status === "ready" ? "green" : "neutral"}>
              政策快照
            </Badge>
            <Badge tone={health?.data_status?.crawler?.status === "ready" ? "green" : "neutral"}>
              爬虫快照
            </Badge>
            <Badge tone="cyan">官方源优先</Badge>
          </div>
        </GlassCard>
      </div>

      <GlassCard title="系统评测" description="模型宏平均与 06B 技术能力指标">
        {gateFailed.length > 0 && (
          <div className="mb-3 flex items-start gap-2 rounded-lg border border-amber-400/30 bg-amber-400/10 p-3 text-xs leading-5 text-amber-200">
            <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              评测门禁未通过：{gateFailed.join("、")}。请在答辩前复核指标口径或重跑
              scripts/build_system_eval.py。
            </span>
          </div>
        )}
        <div className="grid gap-3 sm:grid-cols-2">
          <SummaryBlock title="模型摘要" data={systemEval?.model_summary} />
          <SummaryBlock title="评测数据" data={systemEval?.system_eval} />
        </div>
      </GlassCard>

      {engineering?.capabilities && (
        <GlassCard title="能力状态" description="数据更新链路各项能力">
          <div className="flex flex-wrap gap-2">
            {Object.entries(engineering.capabilities).map(([key, value]) => (
              <CapabilityBadge key={key} label={key} value={value} />
            ))}
          </div>
        </GlassCard>
      )}
    </div>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: typeof HeartPulse;
  label: string;
  value: string;
  tone: "green" | "red" | "amber" | "cyan" | "neutral";
}) {
  const color = {
    green: "text-emerald-300",
    red: "text-red-300",
    amber: "text-amber-300",
    cyan: "text-accent",
    neutral: "text-slate-300",
  }[tone];
  return (
    <GlassCard className="p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-slate-400">{label}</p>
          <p className={`tabular mt-1 text-xl font-extrabold ${color}`}>{value}</p>
        </div>
        <div className="glass-inset grid h-10 w-10 shrink-0 place-items-center rounded-lg text-accent">
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </GlassCard>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-white/[.06] pb-2 last:border-0">
      <span className="text-xs font-semibold text-slate-500">{label}</span>
      <span className="text-right text-slate-200">{value}</span>
    </div>
  );
}

function SummaryBlock({ title, data }: { title: string; data?: Record<string, unknown> }) {
  return (
    <div className="glass-soft p-3">
      <p className="mb-2 text-[11px] font-semibold text-slate-500">{title}</p>
      {data && Object.keys(data).length > 0 ? (
        <div className="grid gap-1.5">
          {Object.entries(data)
            .slice(0, 12)
            .map(([key, value]) => (
              <SummaryRow key={key} label={key} value={value} depth={0} />
            ))}
        </div>
      ) : (
        <p className="text-xs text-slate-500">暂无数据</p>
      )}
    </div>
  );
}

function SummaryRow({ label, value, depth }: { label: string; value: unknown; depth: number }) {
  // 嵌套对象/数组递归展开为缩进子树，避免渲染成 [object Object]
  if (value !== null && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) {
      return (
        <div className="flex justify-between gap-3 text-xs">
          <span className="truncate text-slate-500">{label}</span>
          <span className="shrink-0 text-slate-600">空</span>
        </div>
      );
    }
    return (
      <div>
        <div className="flex items-center justify-between gap-3 text-xs">
          <span className="truncate text-slate-500">{label}</span>
          <span className="shrink-0 text-[10px] text-slate-600">
            {Array.isArray(value) ? `${entries.length} 项` : "明细"}
          </span>
        </div>
        <div className="mt-0.5 border-l border-white/[.08] pl-2.5">
          {entries.slice(0, 8).map(([childKey, childValue]) => (
            <SummaryRow key={childKey} label={childKey} value={childValue} depth={depth + 1} />
          ))}
          {entries.length > 8 && (
            <p className="text-[10px] text-slate-600">… 其余 {entries.length - 8} 项</p>
          )}
        </div>
      </div>
    );
  }
  return (
    <div className="flex justify-between gap-3 text-xs">
      <span className="truncate text-slate-500">{label}</span>
      <span className="tabular shrink-0 text-slate-300">
        {typeof value === "number" ? Number.isFinite(value) ? value.toFixed(2) : String(value) : formatScalar(value)}
      </span>
    </div>
  );
}

function CapabilityBadge({ label, value }: { label: string; value: unknown }) {
  // 嵌套对象（如 policy_cost/compliance）展开为子项 Badge，避免 [object Object]
  if (value !== null && typeof value === "object" && !Array.isArray(value)) {
    const entries = Object.entries(value as Record<string, unknown>);
    return (
      <>
        {entries.map(([childKey, childValue]) => (
          <Badge key={`${label}.${childKey}`} tone={isReady(childValue) ? "green" : "neutral"}>
            {label}.{childKey}: {formatScalar(childValue)}
          </Badge>
        ))}
      </>
    );
  }
  return (
    <Badge tone={isReady(value) ? "green" : "neutral"}>
      {label}: {formatScalar(value)}
    </Badge>
  );
}

function formatScalar(value: unknown): string {
  if (value === null || value === undefined) return "--";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function formatFiles(files?: Record<string, boolean>): string {
  if (!files) return "--";
  const entries = Object.entries(files);
  return `${entries.filter(([, ok]) => ok).length}/${entries.length} 就绪`;
}

function isReady(value: unknown): boolean {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") return ["ok", "ready", "enabled", "true"].includes(value.toLowerCase());
  return false;
}

function OfflineNotice() {
  return (
    <GlassCard>
      <div className="flex items-center gap-3">
        <ShieldCheck className="h-6 w-6 text-amber-300" />
        <div>
          <p className="text-sm font-bold text-white">在线模式可用</p>
          <p className="mt-1 text-xs text-slate-400">
            系统控制台需要连接 FastAPI 后端，离线单文件仅保留现有快照能力。
          </p>
        </div>
      </div>
    </GlassCard>
  );
}
