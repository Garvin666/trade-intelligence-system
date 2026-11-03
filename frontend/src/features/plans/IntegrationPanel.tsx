import { useState, type ReactNode } from "react";
import {
  Bot,
  Boxes,
  Copy,
  Database,
  ExternalLink,
  ListChecks,
  PlugZap,
  Server,
  type LucideIcon,
} from "lucide-react";
import {
  useAiConfig,
  useDataStatus,
  useJobs,
  useSystemStatus,
} from "@/shared/api/hooks";
import { AiConfigPanel } from "@/features/ai-config/AiConfigPanel";
import { useTransitionNavigate } from "@/widgets/RouteTransition";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTrigger,
} from "@/shared/ui/dialog";
import { GlassCard } from "@/shared/ui/glass-card";
import {
  coverageLabel,
  fallbackLabel,
  jobLabel,
  jobTone,
  providerLabel,
  sourceStatusLabel,
  sourceTone,
  type StatusTone,
} from "./integrationStatus";

export function IntegrationPanel({
  showSystemLink = true,
}: {
  showSystemLink?: boolean;
}) {
  const transitionNavigate = useTransitionNavigate();
  const { data: systemStatus, isLoading: statusLoading } = useSystemStatus();
  const { data: aiStatus } = useAiConfig();
  const { data: dataStatus } = useDataStatus();
  const { data: jobsPayload } = useJobs();
  const [copied, setCopied] = useState(false);

  const jobs = jobsPayload?.items ?? [];
  const health = systemStatus?.health;
  const backendStatus = health?.status;
  const mcpMounted = health?.mcp === true;
  const supplierStatus = dataStatus?.suppliers as
    | Record<string, unknown>
    | undefined;
  const supplierRows = systemStatus?.suppliers?.rows ?? [];
  const supplierRowCount = Array.isArray(supplierRows)
    ? supplierRows.length
    : typeof supplierStatus?.rows === "number"
      ? supplierStatus.rows
      : 0;
  const supplierErrors = Array.isArray(supplierStatus?.errors)
    ? supplierStatus.errors.length
    : 0;
  const platformRankings = dataStatus?.platform_rankings as
    | Record<string, unknown>
    | undefined;
  const platformProviders =
    (platformRankings?.providers as
      | Record<string, { status?: string }>
      | undefined) ?? {};
  const platformValues = Object.values(platformProviders);
  const platformTone: StatusTone = platformValues.some(
    (provider) => provider?.status === "error",
  )
    ? "red"
    : platformValues.some(
          (provider) =>
            provider?.status === "fallback" || provider?.status === "mock",
        )
      ? "amber"
      : platformValues.length
        ? "green"
        : "neutral";

  const dataSourceRows = [
    {
      label: "联网快照",
      status: dataStatus?.online?.status,
      provider: dataStatus?.online?.provider,
      fallbackUsed: dataStatus?.online?.fallback_used,
      coverage: dataStatus?.online?.sources_count,
    },
    {
      label: "Google Trends",
      status: dataStatus?.trends?.status,
      provider: dataStatus?.trends?.provider,
      fallbackUsed: dataStatus?.trends?.fallback_used,
      coverage: dataStatus?.trends?.coverage,
    },
    {
      label: "平台榜单",
      status:
        platformTone === "red"
          ? "error"
          : platformTone === "amber"
            ? "fallback"
            : platformTone === "green"
              ? "ready"
              : undefined,
      provider: platformValues.length ? "github" : undefined,
      fallbackUsed: platformRankings?.fallback_used,
      coverage: platformRankings?.rows,
    },
    {
      label: "海关出口",
      status: dataStatus?.customs?.status,
      provider: dataStatus?.customs?.provider,
      fallbackUsed: dataStatus?.customs?.fallback_used,
      coverage: dataStatus?.customs?.rows,
    },
    {
      label: "政策雷达",
      status: dataStatus?.policy?.status,
      provider: dataStatus?.policy?.provider,
      fallbackUsed: dataStatus?.policy?.fallback_used,
      coverage: dataStatus?.policy?.events,
    },
  ];

  const jobRows = [
    { name: "daily_update", label: "每日数据更新" },
    { name: "market_daily", label: "市场日报" },
    { name: "control_run", label: "对照组评测" },
    { name: "policy_refresh", label: "政策雷达" },
  ].map((item) => ({
    ...item,
    status: jobs.find((job) => job.name === item.name)?.status ?? "idle",
  }));

  const aiConfigured = aiStatus?.configured === true;
  const aiDetail = aiConfigured
    ? `${aiStatus?.model ?? "--"} · ${aiStatus?.base_url ?? "--"}`
    : "未配置模型，AI 调用将回退规则引擎";

  const openApiDocs = () => {
    window.open("/docs", "_blank", "noopener,noreferrer");
  };

  const copyMcpEndpoint = async () => {
    const endpoint = `${window.location.origin}/mcp`;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(endpoint);
      } else {
        const textarea = document.createElement("textarea");
        textarea.value = endpoint;
        textarea.style.position = "fixed";
        textarea.style.opacity = "0";
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand?.("copy");
        textarea.remove();
      }
      setCopied(true);
    } catch {
      setCopied(true);
    }
    window.setTimeout(() => setCopied(false), 1600);
  };

  return (
    <>
      <GlassCard
        title="真实能力对接"
        description="仅展示当前后端已实现并可调用的能力"
        strong
      >
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
          <CapabilityCard
            icon={Server}
            title="REST API"
            statusText={
              backendStatus === "ok"
                ? "在线"
                : statusLoading
                  ? "加载中"
                  : "未知"
            }
            tone={backendStatus === "ok" ? "green" : "neutral"}
            detail={
              backendStatus === "ok"
                ? "统一后端在线，接口可调用"
                : "等待后端健康状态"
            }
          >
            <Button size="sm" variant="outline" onClick={openApiDocs}>
              <ExternalLink className="h-3.5 w-3.5" />
              打开 API 文档
            </Button>
          </CapabilityCard>

          <CapabilityCard
            icon={PlugZap}
            title="MCP Server"
            statusText={
              mcpMounted ? "已挂载" : statusLoading ? "加载中" : "未挂载"
            }
            tone={mcpMounted ? "green" : statusLoading ? "neutral" : "amber"}
            detail="Streamable HTTP · /mcp"
          >
            <Button size="sm" variant="outline" onClick={copyMcpEndpoint}>
              <Copy className="h-3.5 w-3.5" />
              {copied ? "已复制" : "复制 MCP 端点"}
            </Button>
          </CapabilityCard>

          <CapabilityCard
            icon={Bot}
            title="AI 接入"
            statusText={aiConfigured ? "已配置" : "未配置"}
            tone={aiConfigured ? "green" : "neutral"}
            detail={aiDetail}
          >
            <Dialog>
              <DialogTrigger asChild>
                <Button size="sm" variant="outline">
                  配置 AI
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader
                  title="AI 接入"
                  description="配置统一模型与搜索参数，配置只保存在当前浏览器会话。"
                />
                <AiConfigPanel />
              </DialogContent>
            </Dialog>
          </CapabilityCard>
        </div>
      </GlassCard>

      <GlassCard
        title="数据源与任务"
        description="状态来自 data_status / health / jobs 实时接口"
        strong
      >
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <div>
            <SectionLabel icon={Database}>数据源</SectionLabel>
            <div className="grid gap-2">
              {dataSourceRows.map((row) => (
                <DataSourceRow key={row.label} {...row} />
              ))}
            </div>
            <div className="mt-3">
              <SupplierStatus
                provider={supplierStatus?.provider}
                coverage={supplierStatus?.coverage}
                rowCount={supplierRowCount}
                errorCount={supplierErrors}
              />
            </div>
            {dataStatus?.as_of_label && (
              <p className="mt-3 text-[11px] text-slate-500">
                {dataStatus.as_of_label}
              </p>
            )}
          </div>

          <div>
            <SectionLabel icon={ListChecks}>后台任务</SectionLabel>
            <div className="grid gap-2">
              {jobRows.map((job) => (
                <JobRow key={job.name} label={job.label} status={job.status} />
              ))}
            </div>
            {showSystemLink && (
              <Button
                size="sm"
                variant="outline"
                className="mt-3"
                onClick={() => transitionNavigate("/system")}
              >
                查看系统控制台
              </Button>
            )}
          </div>
        </div>
      </GlassCard>
    </>
  );
}

export function OfflineIntegrationPanel() {
  return (
    <GlassCard
      title="真实能力对接"
      description="在线模式可用"
      strong
    >
      <div className="flex items-start gap-3">
        <PlugZap className="mt-0.5 h-5 w-5 shrink-0 text-accent" />
        <p className="text-sm leading-6 text-slate-400">
          离线单文件仅保留本地方案数据；连接统一后端后，可查看 REST API、MCP、
          AI 接入与数据源实时状态。
        </p>
      </div>
    </GlassCard>
  );
}

function CapabilityCard({
  icon: Icon,
  title,
  statusText,
  tone,
  detail,
  children,
}: {
  icon: LucideIcon;
  title: string;
  statusText: string;
  tone: StatusTone;
  detail: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="glass-soft p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <Icon className="h-4 w-4 shrink-0 text-accent" />
          <p className="truncate text-sm font-bold text-white">{title}</p>
        </div>
        <Badge tone={tone} className="shrink-0">
          {statusText}
        </Badge>
      </div>
      <p className="mt-1 truncate text-[11px] text-slate-500">{detail}</p>
      <div className="mt-3">{children}</div>
    </div>
  );
}

function SectionLabel({
  icon: Icon,
  children,
}: {
  icon: LucideIcon;
  children: ReactNode;
}) {
  return (
    <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-slate-400">
      <Icon className="h-3.5 w-3.5 text-accent" />
      {children}
    </div>
  );
}

function DataSourceRow({
  label,
  status,
  provider,
  fallbackUsed,
  coverage,
}: {
  label: string;
  status?: unknown;
  provider?: unknown;
  fallbackUsed?: unknown;
  coverage?: unknown;
}) {
  const tone = sourceTone({ status, provider, fallbackUsed });
  return (
    <div className="glass-soft flex items-center justify-between gap-2 p-2.5">
      <div className="min-w-0">
        <p className="text-xs font-semibold text-white">{label}</p>
        <p className="mt-0.5 truncate text-[11px] text-slate-500">
          {providerLabel(provider)} · {fallbackLabel(fallbackUsed)} ·{" "}
          {coverageLabel(coverage)}
        </p>
      </div>
      <Badge tone={tone} className="shrink-0">
        {sourceStatusLabel({ status, provider, fallbackUsed })}
      </Badge>
    </div>
  );
}

function SupplierStatus({
  provider,
  coverage,
  rowCount,
  errorCount,
}: {
  provider?: unknown;
  coverage?: unknown;
  rowCount: number;
  errorCount: number;
}) {
  const tone =
    String(provider ?? "").toLowerCase() === "mock"
      ? "amber"
      : sourceTone({ provider, errorCount });
  return (
    <div className="glass-soft p-2.5">
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <Boxes className="h-4 w-4 shrink-0 text-accent" />
          <p className="truncate text-xs font-semibold text-white">1688 货源</p>
        </div>
        <Badge tone={tone} className="shrink-0">
          {providerLabel(provider)}
        </Badge>
      </div>
      <p className="mt-1 truncate text-[11px] text-slate-500">
        {providerLabel(provider)} · {coverageLabel(coverage)} · {rowCount} 行
        {errorCount > 0 ? ` · ${errorCount} 条错误` : ""}
      </p>
    </div>
  );
}

function JobRow({ label, status }: { label: string; status?: unknown }) {
  return (
    <div className="glass-soft flex items-center justify-between gap-2 p-2.5">
      <span className="text-xs font-semibold text-white">{label}</span>
      <Badge tone={jobTone(status)} className="shrink-0">
        {jobLabel(status)}
      </Badge>
    </div>
  );
}
