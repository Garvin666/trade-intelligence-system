import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  Check,
  ClipboardCopy,
  Download,
  FileText,
  Play,
  RefreshCcw,
  Square,
  Sparkles,
  Wand2,
} from "lucide-react";
import {
  exportLaunchReport,
  streamLaunchReport,
} from "@/shared/api/client";
import type {
  LaunchReportResult,
  LaunchReportStreamPhase,
} from "@/shared/api/types";
import { useAiConfig, useExamples, useTradeCatalog } from "@/shared/api/hooks";
import { IS_OFFLINE } from "@/shared/api/offline";
import { categoryName, fallbackCategoryOptions } from "@/shared/lib/names";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { GlassCard } from "@/shared/ui/glass-card";
import { Select } from "@/shared/ui/select";
import { useTradeIntelStore } from "@/shared/store/trade-intel";
import { PagedMarkdown } from "./PagedMarkdown";
import {
  LAUNCH_EXAMPLES,
  LAUNCH_FIELD_LABELS,
  LAUNCH_FIELD_ORDER,
  LAUNCH_OUTPUT_FORMATS,
  LAUNCH_SECTIONS,
  LAUNCH_STYLES,
  LAUNCH_TEMPLATE,
  buildLaunchPrompt,
  type LaunchFields,
  type LaunchSectionKey,
} from "./launchTemplate";

const MARKET_OPTIONS = [
  ["us", "美国"],
  ["eu", "欧洲"],
  ["sea", "东南亚"],
  ["jp", "日本"],
  ["ca", "加拿大"],
  ["au", "澳大利亚"],
  ["uk", "英国"],
  ["kr", "韩国"],
  ["de", "德国"],
  ["fr", "法国"],
  ["vn", "越南"],
  ["ru", "俄罗斯"],
  ["hu", "匈牙利"],
  ["ae", "中东"],
  ["mx", "墨西哥"],
].map(([value, label]) => ({ value, label }));

const ALL_SECTIONS = LAUNCH_SECTIONS.map((section) => section.value);

function emptyFields(): LaunchFields {
  return {
    market: "",
    category: "",
    product: "",
    competitors: "",
    reviews: "",
    costs: "",
    keywords: "",
    sections: [...ALL_SECTIONS],
    style: "logic",
    output_format: "markdown",
  };
}

function normalizeLaunchFields(fields: Record<string, unknown>): LaunchFields {
  const base = emptyFields();
  const sections = Array.isArray(fields.sections)
    ? (fields.sections as LaunchSectionKey[]).filter((item) =>
        ALL_SECTIONS.includes(item),
      )
    : base.sections;
  return {
    market: String(fields.market ?? base.market),
    market_custom: fields.market_custom ? String(fields.market_custom) : undefined,
    category: String(fields.category ?? base.category),
    category_custom: fields.category_custom
      ? String(fields.category_custom)
      : undefined,
    product: String(fields.product ?? ""),
    competitors: String(fields.competitors ?? ""),
    reviews: String(fields.reviews ?? ""),
    costs: String(fields.costs ?? ""),
    keywords: String(fields.keywords ?? ""),
    sections: sections.length ? sections : base.sections,
    style:
      fields.style === "brief" || fields.style === "strategy"
        ? fields.style
        : "logic",
    output_format:
      fields.output_format === "checklist" || fields.output_format === "table"
        ? fields.output_format
        : "markdown",
  };
}

function readableError(error: unknown): string {
  const raw = error instanceof Error ? error.message : String(error);
  try {
    const parsed = JSON.parse(raw) as { detail?: string; error?: string };
    const detail = parsed.detail ?? parsed.error;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
  } catch {
    // keep raw message
  }
  return raw || "生成失败，请检查 AI 配置后重试。";
}

export function LaunchReportPanel() {
  const { data: aiStatus } = useAiConfig();
  const { data: catalog } = useTradeCatalog();
  const categoryOptions = useMemo(() => {
    const items = catalog?.data?.categories ?? [];
    if (items.length) {
      return items
        .filter((item) => item.key)
        .map((item) => ({ value: item.key, label: String(item.label ?? categoryName(item.key)) }));
    }
    return fallbackCategoryOptions;
  }, [catalog]);

  const { data: examples } = useExamples();
  const lastFourBrainResult = useTradeIntelStore(
    (state) => state.lastFourBrainResult,
  );
  const setLaunchDraft = useTradeIntelStore((state) => state.setLaunchDraft);
  const [fields, setFields] = useState<LaunchFields>(() => emptyFields());
  const [presetId, setPresetId] = useState("");
  const [template, setTemplate] = useState(LAUNCH_TEMPLATE);
  const [templateOpen, setTemplateOpen] = useState(false);
  const [promptOpen, setPromptOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [streamPhase, setStreamPhase] = useState<LaunchReportStreamPhase | "idle">(
    "idle",
  );
  const [streamChars, setStreamChars] = useState(0);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [liveReport, setLiveReport] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [result, setResult] = useState<LaunchReportResult | null>(null);
  const [copied, setCopied] = useState<"prompt" | "report" | null>(null);
  const [filledFromFourBrain, setFilledFromFourBrain] = useState(false);
  const copyTimer = useRef<number | null>(null);
  const fourBrainTimer = useRef<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const elapsedTimer = useRef<number | null>(null);
  const startedAtRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      abortRef.current = null;
      if (elapsedTimer.current !== null) {
        window.clearInterval(elapsedTimer.current);
        elapsedTimer.current = null;
      }
    };
  }, []);

  const launchPresets = useMemo(() => {
    const remote = (examples?.launch_report ?? []).map((item, index) => {
      const typed = item as unknown as {
        id?: string;
        label?: string;
        fields?: { product?: unknown };
      };
      return {
        id: String(typed.id ?? `remote_${index}`),
        label: String(typed.label ?? typed.fields?.product ?? `示例 ${index + 1}`),
        fields: normalizeLaunchFields(
          (typed.fields ?? {}) as Record<string, unknown>,
        ),
      };
    });
    const local = LAUNCH_EXAMPLES.map((item, index) => ({
      id: `local_${index}`,
      label: item.product || `示例 ${index + 1}`,
      fields: item,
    }));
    const merged = [...remote];
    local.forEach((item) => {
      if (!merged.some((preset) => preset.label === item.label)) {
        merged.push(item);
      }
    });
    return merged;
  }, [examples]);

  const prompt = useMemo(
    () => buildLaunchPrompt(fields, template),
    [fields, template],
  );
  const aiReady = !IS_OFFLINE && aiStatus?.configured === true;

  const setField = (key: keyof LaunchFields, value: string | string[]) => {
    setFields((prev) => ({ ...prev, [key]: value }));
  };

  const toggleSection = (section: LaunchSectionKey) => {
    setFields((prev) => {
      const has = prev.sections.includes(section);
      return {
        ...prev,
        sections: has
          ? prev.sections.filter((item) => item !== section)
          : [...prev.sections, section],
      };
    });
  };

  const fillExample = (preset: { fields: LaunchFields }) => {
    setFields(preset.fields);
    setResult(null);
    setError(null);
  };

  const fillFromFourBrain = () => {
    const result = lastFourBrainResult as Record<string, unknown> | null;
    if (!result) return;
    const payload = (result.payload ?? {}) as Record<string, unknown>;
    const realEvidence = (result.real_evidence ?? {}) as Record<string, unknown>;
    const market = String(
      realEvidence.market ?? payload.market ?? result.market ?? "",
    );
    const category = String(
      result.category ?? payload.category ?? "",
    );
    const product = String(
      payload.keyword ?? result.keyword ?? "",
    );
    const unitCost = Number(
      payload.unit_cost ?? result.unit_cost ?? 0,
    );
    setFields((prev) => ({
      ...prev,
      market: market || prev.market,
      market_custom: prev.market_custom || "基于四脑分析结论",
      category: category || prev.category,
      category_custom: prev.category_custom || String(result.category_name ?? ""),
      product: product || prev.product,
      costs: prev.costs || String(unitCost > 0 ? `采购成本 ¥${unitCost}/件` : ""),
      keywords:
        prev.keywords || String(product ? `候选词：${product}` : ""),
    }));
    setLaunchDraft({ source: "four-brain", ...(result as Record<string, unknown>) });
    setError(null);
    setFilledFromFourBrain(true);
    if (fourBrainTimer.current !== null) {
      window.clearTimeout(fourBrainTimer.current);
    }
    fourBrainTimer.current = window.setTimeout(
      () => setFilledFromFourBrain(false),
      1600,
    );
  };

  const copyToClipboard = async (text: string, kind: "prompt" | "report") => {
    let ok: boolean;
    try {
      await navigator.clipboard.writeText(text);
      ok = true;
    } catch {
      ok = fallbackCopy(text);
    }
    if (ok) {
      if (copyTimer.current !== null) {
        window.clearTimeout(copyTimer.current);
      }
      setCopied(kind);
      copyTimer.current = window.setTimeout(() => setCopied(null), 1600);
    }
  };

  const startElapsedTimer = () => {
    startedAtRef.current = Date.now();
    if (elapsedTimer.current !== null) {
      window.clearInterval(elapsedTimer.current);
    }
    elapsedTimer.current = window.setInterval(() => {
      setElapsedMs(Date.now() - (startedAtRef.current ?? Date.now()));
    }, 200);
  };

  const stopElapsedTimer = () => {
    if (elapsedTimer.current !== null) {
      window.clearInterval(elapsedTimer.current);
      elapsedTimer.current = null;
    }
  };

  const stop = () => {
    abortRef.current?.abort();
    abortRef.current = null;
    stopElapsedTimer();
    setLoading(false);
    setStreamPhase("idle");
    setLiveReport(null);
    setStreamChars(0);
  };

  const run = async () => {
    if (loading || !aiReady) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setLiveReport("");
    setStreamPhase("connecting");
    setStreamChars(0);
    setElapsedMs(0);
    startElapsedTimer();
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const data = await streamLaunchReport(
        { prompt },
        {
          onStatus: (status) => {
            setStreamPhase(status.phase);
            if (typeof status.elapsed_ms === "number") {
              setElapsedMs(status.elapsed_ms);
            }
            if (typeof status.chars === "number") {
              setStreamChars(status.chars);
            }
          },
          onDelta: (content) => {
            setStreamChars((prev) => prev + content.length);
            setLiveReport((prev) => `${prev ?? ""}${content}`);
          },
        },
        controller.signal,
      );
      stopElapsedTimer();
      setElapsedMs(Date.now() - (startedAtRef.current ?? Date.now()));
      setResult(data);
      setLiveReport(null);
      setStreamPhase("done");
    } catch (err) {
      if (!controller.signal.aborted) {
        setError(readableError(err));
      }
    } finally {
      stopElapsedTimer();
      abortRef.current = null;
      setLoading(false);
    }
  };

  const runExport = async () => {
    if (!result) return;
    setExporting(true);
    setError(null);
    try {
      const blob = await exportLaunchReport({
        format: "pdf",
        report: result.report,
        generated_at: result.generated_at,
      });
      saveBlob(blob, "launch_report.pdf");
    } catch (err) {
      setError(readableError(err));
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[420px_1fr]">
      <GlassCard
        title="立项输入"
        description="下拉选择 + 自由填写，按需勾选报告章节"
        className="h-fit"
      >
        <div className="grid gap-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={LAUNCH_FIELD_LABELS.market}>
              <Select
                value={fields.market}
                onValueChange={(value) => setField("market", value)}
                options={[
                  ...MARKET_OPTIONS,
                  { value: "custom", label: "自定义市场" },
                ]}
                ariaLabel={LAUNCH_FIELD_LABELS.market}
              />
            </Field>
            <Field label={LAUNCH_FIELD_LABELS.category}>
              <Select
                value={fields.category}
                onValueChange={(value) => setField("category", value)}
                options={[
                  ...categoryOptions,
                  { value: "custom", label: "自定义类目" },
                ]}
                ariaLabel={LAUNCH_FIELD_LABELS.category}
              />
            </Field>
          </div>
          {fields.market === "custom" && (
            <Field label="自定义市场名称">
              <input
                value={fields.market_custom ?? ""}
                onChange={(event) => setField("market_custom", event.target.value)}
                className="glass-inset focus-ring h-10 w-full px-3 text-sm"
              />
            </Field>
          )}
          {fields.category === "custom" && (
            <Field label="自定义类目名称">
              <input
                value={fields.category_custom ?? ""}
                onChange={(event) => setField("category_custom", event.target.value)}
                className="glass-inset focus-ring h-10 w-full px-3 text-sm"
              />
            </Field>
          )}
          <Field label={LAUNCH_FIELD_LABELS.product}>
            <input
              value={fields.product}
              onChange={(event) => setField("product", event.target.value)}
              className="glass-inset focus-ring h-10 w-full px-3 text-sm"
            />
          </Field>

          {LAUNCH_FIELD_ORDER.filter((key) =>
            ["competitors", "reviews", "costs", "keywords"].includes(key),
          ).map((key) => (
            <Field key={key} label={LAUNCH_FIELD_LABELS[key]}>
              <textarea
                value={fields[key]}
                onChange={(event) => setField(key, event.target.value)}
                rows={key === "competitors" ? 4 : 3}
                className="glass-inset focus-ring w-full resize-y px-3 py-2.5 text-sm leading-6 text-slate-200"
              />
            </Field>
          ))}

          <div className="grid gap-2">
            <p className="text-xs font-semibold text-slate-400">报告章节</p>
            <div className="grid gap-2 sm:grid-cols-2">
              {LAUNCH_SECTIONS.map((section) => {
                const selected = fields.sections.includes(section.value);
                return (
                  <label
                    key={section.value}
                    className="glass-soft flex cursor-pointer items-start gap-2 rounded-lg p-2.5"
                  >
                    <input
                      type="checkbox"
                      checked={selected}
                      onChange={() => toggleSection(section.value)}
                      className="mt-0.5 accent-cyan-400"
                    />
                    <span className="min-w-0">
                      <span className="block text-xs font-semibold text-slate-200">
                        {section.label}
                      </span>
                      <span className="block text-[10px] leading-4 text-slate-500">
                        {section.description}
                      </span>
                    </span>
                  </label>
                );
              })}
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="报告风格">
              <Select
                value={fields.style}
                onValueChange={(value) =>
                  setField("style", value as LaunchFields["style"])
                }
                options={LAUNCH_STYLES.map((item) => ({
                  value: item.value,
                  label: item.label,
                }))}
              />
            </Field>
            <Field label="输出结构">
              <Select
                value={fields.output_format}
                onValueChange={(value) =>
                  setField("output_format", value as LaunchFields["output_format"])
                }
                options={LAUNCH_OUTPUT_FORMATS.map((item) => ({
                  value: item.value,
                  label: item.label,
                }))}
              />
            </Field>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <Select
              value={presetId}
              onValueChange={(value) => {
                const preset = launchPresets.find((item) => item.id === value);
                if (preset) {
                  setPresetId(value);
                  fillExample(preset);
                }
              }}
              options={launchPresets.map((item) => ({
                value: item.id,
                label: item.label,
              }))}
              placeholder="选择立项示例"
              ariaLabel="选择立项示例"
            />
            <Button
              variant="secondary"
              onClick={() => {
                if (launchPresets[0]) {
                  setPresetId(launchPresets[0].id);
                  fillExample(launchPresets[0]);
                }
              }}
            >
              <Wand2 className="h-4 w-4" />
              填充示例
            </Button>
          </div>
          <Button
            variant="secondary"
            onClick={fillFromFourBrain}
            disabled={!lastFourBrainResult}
          >
            {filledFromFourBrain ? (
              <Check className="h-4 w-4" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            {filledFromFourBrain ? "已填充" : "从四脑结论填充"}
          </Button>
          {!lastFourBrainResult && (
            <p className="text-[11px] leading-4 text-slate-500">
              先在工作台完成一次四脑分析，再回到这里即可一键带回结论。
            </p>
          )}

          {IS_OFFLINE ? (
            <p className="rounded-lg border border-amber-300/20 bg-amber-400/10 p-3 text-xs leading-5 text-amber-200">
              离线模式仅支持复制提示词，请通过在线后端配置 AI 后生成报告。
            </p>
          ) : aiReady ? (
            <p className="rounded-lg border border-emerald-300/20 bg-emerald-400/10 p-3 text-xs leading-5 text-emerald-200">
              AI 已连接：{aiStatus?.model || "已配置模型"}
              {aiStatus?.base_url ? `（${aiStatus.base_url}）` : ""}。
            </p>
          ) : (
            <p className="rounded-lg border border-amber-300/20 bg-amber-400/10 p-3 text-xs leading-5 text-amber-200">
              AI 未配置：请先在上方「AI 接入」完成配置。
            </p>
          )}

          <div className="grid grid-cols-2 gap-2">
            <Button
              variant="secondary"
              onClick={() => copyToClipboard(prompt, "prompt")}
            >
              <ClipboardCopy className="h-4 w-4" />
              {copied === "prompt" ? "已复制" : "复制提示词"}
            </Button>
            <Button
              variant="secondary"
              onClick={() => setPromptOpen((value) => !value)}
            >
              <FileText className="h-4 w-4" />
              预览提示词
            </Button>
          </div>

          {promptOpen && (
            <pre className="glass-inset max-h-72 overflow-auto whitespace-pre-wrap break-words p-3 text-xs leading-5 text-slate-300">
              {prompt}
            </pre>
          )}

          <Button onClick={run} disabled={loading || !aiReady} className="w-full">
            <Play className="h-4 w-4" />
            {loading ? "生成中..." : "生成报告"}
          </Button>

          <div className="glass-soft p-3">
            <button
              type="button"
              className="focus-ring flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-xs font-semibold text-slate-300 hover:bg-white/10"
              onClick={() => setTemplateOpen((value) => !value)}
            >
              <span className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-accent" />
                编辑完整模板（高级）
              </span>
              <span>{templateOpen ? "收起" : "展开"}</span>
            </button>
            {templateOpen && (
              <div className="mt-3 grid gap-2">
                <textarea
                  value={template}
                  onChange={(event) => setTemplate(event.target.value)}
                  rows={14}
                  className="glass-inset focus-ring w-full resize-y px-3 py-2.5 text-xs leading-5 text-slate-200"
                />
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setTemplate(LAUNCH_TEMPLATE)}
                >
                  <RefreshCcw className="h-3.5 w-3.5" />
                  恢复默认模板
                </Button>
              </div>
            )}
          </div>
        </div>
      </GlassCard>

      <GlassCard
        title="立项报告"
        description="生成内容为纯 AI 输出，数据与结论需人工核验"
        strong
        className="min-w-0"
      >
        {error && (
          <div className="rounded-lg border border-red-300/20 bg-red-500/10 p-3 text-sm leading-6 text-red-200">
            {error}
          </div>
        )}
        {loading && (
          <div className="grid gap-3">
            <div className="glass-soft flex flex-wrap items-center gap-3 p-3">
              <span className="relative flex h-2.5 w-2.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-cyan-400 opacity-60" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-cyan-300" />
              </span>
              <span className="text-xs font-semibold text-slate-200">
                {streamPhase === "connecting"
                  ? "正在连接 AI · 等待首个字符"
                  : "AI 正在生成报告"}
              </span>
              <span className="font-mono text-[11px] text-slate-400">
                {(elapsedMs / 1000).toFixed(1)}s
              </span>
              <span className="font-mono text-[11px] text-slate-400">
                {streamChars} 字符
              </span>
              <Button
                variant="outline"
                size="sm"
                className="ml-auto"
                onClick={stop}
              >
                <Square className="h-3.5 w-3.5" />
                停止生成
              </Button>
            </div>
            {liveReport ? (
              <div className="min-h-48">
                <PagedMarkdown content={liveReport} />
              </div>
            ) : (
              <div className="flex min-h-48 items-center justify-center">
                <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent/30 border-t-cyan-300" />
              </div>
            )}
          </div>
        )}
        {!result && !loading && (
          <div className="flex min-h-48 flex-col items-center justify-center gap-2 text-center">
            <FileText className="h-8 w-8 text-accent/60" />
            <p className="text-sm text-slate-400">
              选择市场 / 类目 / 章节后点击“生成报告”。
            </p>
          </div>
        )}
        {result && !loading && (
          <div className="grid gap-4">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="cyan">Codex 直出（逻辑版）</Badge>
              {result.generated_at && (
                <span className="font-mono text-[10px] text-slate-500">
                  {result.generated_at}
                </span>
              )}
              <Button
                variant="outline"
                size="sm"
                className="ml-auto"
                onClick={() => copyToClipboard(result.report, "report")}
              >
                <ClipboardCopy className="h-3.5 w-3.5" />
                {copied === "report" ? "已复制" : "复制报告"}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={runExport}
                disabled={exporting || IS_OFFLINE}
              >
                <Download className="h-3.5 w-3.5" />
                {exporting ? "导出中..." : "导出 PDF"}
              </Button>
            </div>
            <PagedMarkdown content={result.report} />
          </div>
        )}
      </GlassCard>
    </div>
  );
}

function fallbackCopy(text: string): boolean {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  const ok = document.execCommand("copy");
  document.body.removeChild(textarea);
  return ok;
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="grid gap-1.5">
      <span className="text-xs font-semibold text-slate-400">{label}</span>
      {children}
    </label>
  );
}
