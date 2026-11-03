import { useState } from "react";
import { Download, FlaskConical, Play } from "lucide-react";
import {
  downloadControlTrainData,
  fetchControlWebSetup,
  saveControlWebResponse,
} from "@/shared/api/client";
import {
  useControlMetrics,
  useControlRunStatus,
  useStartControlRun,
} from "@/shared/api/hooks";
import { IS_OFFLINE } from "@/shared/api/offline";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { GlassCard } from "@/shared/ui/glass-card";
import { Select } from "@/shared/ui/select";

export function ControlBenchmarkPanel() {
  const metrics = useControlMetrics();
  const runStatus = useControlRunStatus();
  const start = useStartControlRun();
  const [mode, setMode] = useState("lite");
  const [runs, setRuns] = useState(2);
  const [temperature, setTemperature] = useState(0.2);
  const [webText, setWebText] = useState("");
  const [webRun, setWebRun] = useState("1");
  const [webResult, setWebResult] = useState<string | null>(null);

  if (IS_OFFLINE) {
    return (
      <GlassCard>
        <p className="text-sm text-slate-400">顶级 AI 对照需要在线后端，离线模式不可用。</p>
      </GlassCard>
    );
  }

  const run = async () => {
    await start.mutateAsync({ mode, runs, temperature });
  };

  const downloadTrain = async () => {
    const blob = await downloadControlTrainData();
    saveBlob(blob, "train_data.csv");
  };

  const saveWeb = async () => {
    if (!webText.trim()) return;
    const result = await saveControlWebResponse({
      run: Number(webRun),
      text: webText.trim(),
    });
    setWebResult(JSON.stringify(result));
    setWebText("");
  };

  return (
    <div className="grid gap-4">
      <GlassCard title="对照组结果" description="顶级 AI 与系统模型在留出期的宏平均对比">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="状态" value={metrics.data?.status ?? "--"} />
          <Stat label="生成时间" value={String(metrics.data?.generated_at ?? "--").slice(0, 16)} />
          <Stat label="总格数" value={String(metrics.data?.total_cells ?? "--")} />
          <Stat label="范围" value={String(metrics.data?.scope ?? "--")} />
        </div>
        {metrics.data?.system_baseline && (
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {Object.entries(metrics.data.system_baseline).map(([key, value]) => (
              <Stat key={key} label={key} value={typeof value === "number" ? value.toFixed(4) : String(value)} />
            ))}
          </div>
        )}
        {metrics.data?.models && (
          <div className="mt-4 grid gap-3">
            {Object.entries(metrics.data.models).map(([key, model]) => (
              <ModelSummary key={key} label={String((model as Record<string, unknown>)?.label ?? key)} model={model} />
            ))}
          </div>
        )}
      </GlassCard>

      <GlassCard title="运行对照组" description="使用 AI 接入中的模型配置启动真实评测">
        <div className="grid gap-4 sm:grid-cols-4">
          <label className="grid gap-1.5">
            <span className="text-xs font-semibold text-slate-400">模式</span>
            <Select
              value={mode}
              onValueChange={setMode}
              options={[
                { value: "lite", label: "lite（12 组合）" },
                {
                  value: "full",
                  label: `full（${String(metrics.data?.total_cells ?? 23760)} 格）`,
                },
              ]}
            />
          </label>
          <label className="grid gap-1.5">
            <span className="text-xs font-semibold text-slate-400">运行次数</span>
            <input
              type="number"
              min={1}
              max={4}
              value={runs}
              onChange={(event) => setRuns(Number(event.target.value))}
              className="glass-inset focus-ring h-10 w-full px-3 text-sm text-slate-200"
            />
          </label>
          <label className="grid gap-1.5">
            <span className="text-xs font-semibold text-slate-400">温度</span>
            <input
              type="number"
              min={0}
              max={2}
              step={0.1}
              value={temperature}
              onChange={(event) => setTemperature(Number(event.target.value))}
              className="glass-inset focus-ring h-10 w-full px-3 text-sm text-slate-200"
            />
          </label>
          <div className="flex items-end">
            <Button className="w-full" disabled={start.isPending} onClick={run}>
              <Play className="h-4 w-4" />
              {start.isPending ? "启动中..." : "启动对照"}
            </Button>
          </div>
        </div>
        {runStatus.data?.status === "running" && (
          <div className="mt-3 flex items-center gap-2 text-xs text-amber-200">
            <Badge tone="amber">运行中</Badge>
            {String(runStatus.data.progress ?? "")}
          </div>
        )}
        {runStatus.data?.error && (
          <p className="mt-3 rounded-lg border border-red-300/20 bg-red-500/10 p-2 text-xs text-red-200">
            {runStatus.data.error}
          </p>
        )}
      </GlassCard>

      <GlassCard
        title="DeepSeek 网页版对照"
        description="无需 API Key，下载训练数据并粘贴网页回复"
        action={
          <Button size="sm" variant="outline" onClick={downloadTrain}>
            <Download className="h-4 w-4" />
            下载训练数据
          </Button>
        }
      >
        <div className="grid gap-3 sm:grid-cols-[120px_1fr_auto]">
          <label className="grid gap-1.5">
            <span className="text-xs font-semibold text-slate-400">轮次</span>
            <select
              value={webRun}
              onChange={(event) => setWebRun(event.target.value)}
              className="glass-inset focus-ring h-10 w-full px-3 text-sm text-slate-200"
            >
              <option value="1">Run 1</option>
              <option value="2">Run 2</option>
            </select>
          </label>
          <label className="grid gap-1.5">
            <span className="text-xs font-semibold text-slate-400">网页回复</span>
            <textarea
              rows={3}
              value={webText}
              onChange={(event) => setWebText(event.target.value)}
              className="glass-inset focus-ring w-full resize-y px-3 py-2 text-sm text-slate-200"
            />
          </label>
          <div className="flex items-end">
            <Button variant="secondary" onClick={saveWeb}>
              <FlaskConical className="h-4 w-4" />
              保存并评分
            </Button>
          </div>
        </div>
        {webResult && <p className="mt-2 break-all text-xs text-slate-400">{webResult}</p>}
        <WebSetupHint />
      </GlassCard>
    </div>
  );
}

function ModelSummary({ label, model }: { label: string; model: unknown }) {
  const record = (model ?? {}) as Record<string, unknown>;
  const runs = (record.runs ?? {}) as Record<string, Record<string, unknown>>;
  const runEntries = Object.entries(runs);
  return (
    <div className="glass-soft p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-bold text-white">{label}</span>
        <Badge tone="cyan">{String(record.api_model_id ?? "")}</Badge>
      </div>
      <div className="mt-2 grid gap-1.5 text-xs">
        {runEntries.map(([run, summary]) => (
          <div key={run} className="flex flex-wrap justify-between gap-2">
            <span className="text-slate-500">Run {run}</span>
            <span className="tabular text-slate-300">
              MAPE {number(summary.mape_macro)} · MAE {number(summary.mae_macro)} · Jaccard {number(summary.recommendation_jaccard)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="glass-inset p-3">
      <p className="text-[11px] font-semibold text-slate-500">{label}</p>
      <p className="tabular mt-1 truncate text-sm font-bold text-white">{value}</p>
    </div>
  );
}

function WebSetupHint() {
  const [setup, setSetup] = useState<Record<string, unknown> | null>(null);
  return (
    <div className="mt-3">
      <Button
        size="sm"
        variant="ghost"
        onClick={async () => {
          const data = await fetchControlWebSetup();
          setSetup(data);
        }}
      >
        查看网页版准备信息
      </Button>
      {setup && <p className="mt-2 whitespace-pre-wrap break-all text-xs text-slate-400">{JSON.stringify(setup, null, 2)}</p>}
    </div>
  );
}

function number(value: unknown): string {
  return typeof value === "number" ? value.toFixed(4) : String(value ?? "--");
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
