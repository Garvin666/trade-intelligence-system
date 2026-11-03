import { useState } from "react";
import { Loader2, Play, Square } from "lucide-react";
import { useJobs, useStartJob, useStopJob } from "@/shared/api/hooks";
import { IS_OFFLINE } from "@/shared/api/offline";
import type { JobSummary } from "@/shared/api/types";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { GlassCard } from "@/shared/ui/glass-card";
import { Progress } from "@/shared/ui/progress";

export function JobsPanel() {
  const { data, isLoading, isError } = useJobs();

  if (IS_OFFLINE) {
    return (
      <GlassCard>
        <p className="text-sm text-slate-400">后台任务面板需要在线后端，离线模式不可用。</p>
      </GlassCard>
    );
  }

  if (isLoading && !data) {
    return <div className="glass h-48 animate-pulse" />;
  }

  if (isError || !data) {
    return (
      <GlassCard>
        <p className="text-sm text-red-300">任务状态加载失败。</p>
      </GlassCard>
    );
  }

  const runnableCount = data.items.filter(
    (job) => job.name === "daily_update" || job.name === "market_daily",
  ).length;

  return (
    <div className="grid gap-4">
      <p className="text-xs text-slate-400">
        后台共 {data.items.length} 项（{runnableCount} 项可启动），运行中的任务每 2 秒自动刷新进度。
      </p>
      <div className="grid gap-4 xl:grid-cols-2">
        {data.items.map((job) => (
          <JobCard key={job.name} job={job} />
        ))}
      </div>
    </div>
  );
}

function JobCard({ job }: { job: JobSummary }) {
  const start = useStartJob();
  const stop = useStopJob();
  const [options, setOptions] = useState<Record<string, string | boolean>>({});

  const setOption = (key: string, value: string | boolean) => {
    setOptions((prev) => ({ ...prev, [key]: value }));
  };

  const runnable = job.name === "daily_update" || job.name === "market_daily";
  const running = job.status === "running";
  const tone = statusTone(job.status);

  return (
    <GlassCard
      title={job.label}
      description={job.name}
      action={<Badge tone={tone}>{job.status}</Badge>}
    >
      <div className="grid gap-3">
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div>
            <p className="text-slate-500">任务 ID</p>
            <p className="font-mono text-slate-300">{job.job_id ?? "--"}</p>
          </div>
          <div>
            <p className="text-slate-500">开始时间</p>
            <p className="text-slate-300">{formatTime(job.started_at)}</p>
          </div>
        </div>

        {job.progress?.message && (
          <div className="glass-inset p-3">
            <div className="mb-2 flex items-center justify-between gap-2 text-xs">
              <span className="text-slate-300">{job.progress.message}</span>
              <span className="font-mono text-accent">{job.progress.stage ?? ""}</span>
            </div>
            <Progress value={stagePercent(job.progress.stage)} />
          </div>
        )}

        {job.error && <p className="rounded-lg border border-red-300/20 bg-red-500/10 p-2 text-xs text-red-200">{job.error}</p>}

        {runnable && (
          <div className="grid gap-2">
            {job.name === "daily_update" && (
              <DailyUpdateOptions options={options} onChange={setOption} />
            )}
            {job.name === "market_daily" && (
              <MarketDailyOptions options={options} onChange={setOption} />
            )}
          </div>
        )}

        <div className="flex items-center justify-end gap-2">
          {runnable && !running && (
            <Button
              size="sm"
              disabled={start.isPending}
              onClick={() => start.mutate({ name: job.name, payload: toPayload(options) })}
            >
              <Play className="h-4 w-4" />
              {start.isPending ? "启动中..." : "启动"}
            </Button>
          )}
          {running && (
            <Button size="sm" variant="danger" disabled={stop.isPending} onClick={() => stop.mutate(job.name)}>
              <Square className="h-4 w-4" />
              {stop.isPending ? "停止中..." : "停止"}
            </Button>
          )}
          {running && (
            <span className="flex items-center gap-1.5 text-xs text-accent">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              运行中
            </span>
          )}
        </div>
      </div>
    </GlassCard>
  );
}

function DailyUpdateOptions({
  options,
  onChange,
}: {
  options: Record<string, string | boolean>;
  onChange: (key: string, value: string | boolean) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-3">
      <CheckField label="离线模式" checked={Boolean(options.offline)} onChange={(value) => onChange("offline", value)} />
      <CheckField label="跳过重训" checked={Boolean(options.skip_pipeline)} onChange={(value) => onChange("skip_pipeline", value)} />
      <CheckField label="跳过重建" checked={Boolean(options.skip_rebuild)} onChange={(value) => onChange("skip_rebuild", value)} />
      <NumberField label="并发数" value={String(options.workers ?? "")} onChange={(value) => onChange("workers", value)} />
      <TextField label="日期 YYYY-MM-DD" value={String(options.date ?? "")} onChange={(value) => onChange("date", value)} />
    </div>
  );
}

function MarketDailyOptions({
  options,
  onChange,
}: {
  options: Record<string, string | boolean>;
  onChange: (key: string, value: string | boolean) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-3">
      <CheckField label="推送 webhook" checked={Boolean(options.push)} onChange={(value) => onChange("push", value)} />
      <TextField label="日期 YYYY-MM-DD" value={String(options.date ?? "")} onChange={(value) => onChange("date", value)} />
    </div>
  );
}

function CheckField({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-xs text-slate-300">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} className="accent-cyan-400" />
      {label}
    </label>
  );
}

function TextField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="grid gap-1">
      <span className="text-[11px] text-slate-500">{label}</span>
      <input value={value} onChange={(event) => onChange(event.target.value)} className="glass-inset focus-ring h-8 w-full px-2 text-xs text-slate-200" />
    </label>
  );
}

function NumberField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return <TextField label={label} value={value} onChange={onChange} />;
}

function toPayload(options: Record<string, string | boolean>): Record<string, unknown> {
  const payload: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(options)) {
    if (key === "date" && value) payload[key] = value;
    else if (key === "workers" && value) payload[key] = Number(value);
    else if (typeof value === "boolean") payload[key] = value;
  }
  return payload;
}

function stagePercent(stage?: string): number {
  const match = /^(\d+)\/(\d+)$/.exec(String(stage ?? ""));
  if (!match) return 0;
  return (Number(match[1]) / Number(match[2])) * 100;
}

function statusTone(status: string): "green" | "amber" | "red" | "cyan" | "neutral" {
  if (status === "done") return "green";
  if (status === "running") return "amber";
  if (status === "error") return "red";
  if (status === "cancelled") return "neutral";
  return "cyan";
}

function formatTime(value?: string | null): string {
  if (!value) return "--";
  return value.replace("T", " ").slice(0, 19);
}
