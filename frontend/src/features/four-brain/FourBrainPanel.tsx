import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { BrainCircuit, MessageSquarePlus, Play, Save, Upload, Wand2 } from "lucide-react";
import { fetchFourBrain } from "@/shared/api/client";
import { IS_OFFLINE } from "@/shared/api/offline";
import { useExamples } from "@/shared/api/hooks";
import { Button } from "@/shared/ui/button";
import { Badge } from "@/shared/ui/badge";
import { GlassCard } from "@/shared/ui/glass-card";
import { Progress } from "@/shared/ui/progress";
import { Select } from "@/shared/ui/select";
import { PageTurnTabs } from "@/shared/ui/page-turn-tabs";
import { AppChart } from "@/shared/charts/AppChart";
import { useTradeIntelStore } from "@/shared/store/trade-intel";
import { parseUserDataFile } from "@/shared/lib/parseUserData";
import type { EChartsOption } from "echarts";
import { MarkdownView } from "./MarkdownView";

const rolePrompts = {
  market: "请以市场分析师身份评估：目标客群、市场规模、增长节奏、最佳切入市场。结论用一句话概括，并给最多 3 条关键证据。",
  sentiment: "请以舆情洞察官身份评估：用户高频痛点、差异化机会、退货与评价管理。结论用一句话概括，并给最多 3 条关键点。",
  supply_chain: "请以供应链评估师身份评估：到岸成本、MOQ、交付周期、认证与供应链风险。结论用一句话概括，并给最多 3 条关键点。",
  finance: "请以财务精算师身份评估：单件利润、毛利率、ROI、回本与现金流。结论用一句话概括，并给最多 3 条关键点。",
};

const roleLabels: Record<keyof typeof rolePrompts, string> = {
  market: "市场分析师",
  sentiment: "舆情洞察官",
  supply_chain: "供应链评估师",
  finance: "财务精算师",
};

interface FourBrainResult {
  keyword?: string;
  market?: string;
  category?: string;
  category_name?: string;
  verdict?: string;
  score?: number;
  summary?: string;
  dimensions?: Record<string, { label: string; score: number; note: string }>;
  arbitration?: {
    verdict?: string;
    score?: number;
    conflicts?: string[];
    direction_scores?: Record<string, number>;
  };
  brains?: Record<
    string,
    {
      name?: string;
      score?: number;
      direction?: string;
      evidence?: string[];
      summary?: string;
      ai_summary?: string;
      conclusion_points?: string[];
      risks?: unknown[];
      opportunities?: unknown[];
      metrics?: Record<string, unknown>;
    }
  >;
  report?: string;
  research?: {
    disabled?: boolean;
    summary?: string;
    sources?: unknown[];
    mock_count?: number;
    mock_used?: boolean;
  };
  real_evidence?: {
    model_available?: boolean;
    training_status?: Record<string, unknown>;
    proxy?: {
      available?: boolean;
      score?: number | null;
      predicted_demand?: number | null;
      level?: string;
      note?: string;
    };
  };
  generated_at?: string;
  charts?: Array<{
    id?: string;
    type?: string;
    title?: string;
    labels?: string[] | Record<string, unknown>;
    series?: Array<{ name?: string; values?: number[] }>;
    values?: number[][];
  }>;
}

export function FourBrainPanel() {
  const selectionDraft = useTradeIntelStore((state) => state.selectionDraft);
  const setSelectionDraft = useTradeIntelStore((state) => state.setSelectionDraft);
  const [keyword, setKeyword] = useState(
    String(selectionDraft?.keyword ?? "辣条（网红休闲零食）"),
  );
  const [market, setMarket] = useState(String(selectionDraft?.market ?? "us"));
  const [price, setPrice] = useState(
    typeof selectionDraft?.price === "number" ? Number(selectionDraft.price) : 39.9,
  );
  const [budget, setBudget] = useState(
    typeof selectionDraft?.budget === "number" ? Number(selectionDraft.budget) : 50000,
  );
  const [targetMargin, setTargetMargin] = useState(
    typeof selectionDraft?.target_margin === "number"
      ? Number(selectionDraft.target_margin) * 100
      : 25,
  );
  const [prompts, setPrompts] = useState(rolePrompts);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<FourBrainResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exampleId, setExampleId] = useState("four_brain_0");
  const [examplePayload, setExamplePayload] = useState<Record<string, unknown> | null>(null);
  const [followUp, setFollowUp] = useState("");
  const [userData, setUserData] = useState<Record<string, unknown> | null>(null);
  const [fileName, setFileName] = useState("");
  const { data: examples } = useExamples();
  const saveBatchRun = useTradeIntelStore((state) => state.saveBatchRun);
  const setLastFourBrainResult = useTradeIntelStore(
    (state) => state.setLastFourBrainResult,
  );
  const runSeqRef = useRef(0);

  const handleKeywordChange = (value: string) => {
    setKeyword(value);
    if (examplePayload && String(examplePayload.keyword ?? "") !== value.trim()) {
      setExamplePayload(null);
      setResult(null);
      setError(null);
    }
  };

  const fourBrainExamples = useMemo(
    () => examples?.four_brain ?? [],
    [examples],
  );
  const exampleOptions = useMemo(
    () =>
      fourBrainExamples.map((item) => ({
        value: String(item.id),
        label: String(item.label ?? item.id),
      })),
    [fourBrainExamples],
  );

  const applyExample = async (id?: string) => {
    const preset = fourBrainExamples.find((item) => item.id === (id ?? exampleId));
    const payload = (preset?.payload ?? {}) as Record<string, unknown>;
    if (!Object.keys(payload).length) return;
    setExampleId(String(preset?.id ?? exampleId));
    setExamplePayload(payload);
    if (payload.keyword) setKeyword(String(payload.keyword));
    if (payload.market) setMarket(String(payload.market));
    if (typeof payload.price_min === "number" && typeof payload.price_max === "number") {
      setPrice((Number(payload.price_min) + Number(payload.price_max)) / 2);
    }
    if (typeof payload.budget === "number") setBudget(Number(payload.budget));
    if (typeof payload.target_margin === "number") {
      setTargetMargin(Number(payload.target_margin) * 100);
    }
    setFollowUp("");
    setResult(null);
    setError(null);
    await runWithPayload(payload, true);
  };

  const handleFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const parsed = await parseUserDataFile(file);
      setUserData(parsed);
      setFileName(file.name);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "用户数据解析失败");
    }
  };

  useEffect(() => {
    if (selectionDraft) setSelectionDraft(null);
  }, [selectionDraft, setSelectionDraft]);

  const runWithPayload = async (payload: Record<string, unknown>, quick: boolean) => {
    const seq = ++runSeqRef.current;
    setLoading(true);
    setError(null);
    try {
      const request = {
        ...payload,
        ai: true,
        research: !quick && !IS_OFFLINE && !userData,
        role_prompts: prompts,
        tools: quick ? [] : ["crawler"],
        max_steps: quick ? 0 : 3,
        ...(userData ? { user_data: userData, use_user_data: true, offline_only: false } : {}),
      };
      const data = await fetchFourBrain(request);
      if (seq !== runSeqRef.current) return;
      setResult(data as FourBrainResult);
      setLastFourBrainResult(data as unknown as Record<string, unknown>);
    } catch (err) {
      if (seq !== runSeqRef.current) return;
      setError(err instanceof Error ? err.message : "四脑分析失败，请检查后端或 AI 配置。");
    } finally {
      if (seq === runSeqRef.current) setLoading(false);
    }
  };

  const run = async (quick = false) => {
    const base = examplePayload ?? {};
    await runWithPayload(
      {
        keyword,
        market,
        price_min: price * 0.8,
        price_max: price * 1.2,
        budget,
        target_margin: targetMargin / 100,
        unit_cost:
          typeof base.unit_cost === "number"
            ? Number(base.unit_cost)
            : price * 0.32,
        freight_per_unit:
          typeof base.freight_per_unit === "number"
            ? Number(base.freight_per_unit)
            : 2.8,
        customs_per_unit:
          typeof base.customs_per_unit === "number"
            ? Number(base.customs_per_unit)
            : 0.9,
        ad_rate: typeof base.ad_rate === "number" ? Number(base.ad_rate) : 0.12,
        return_rate:
          typeof base.return_rate === "number" ? Number(base.return_rate) : 0.03,
        moq: typeof base.moq === "number" ? Number(base.moq) : 500,
        lead_time_days:
          typeof base.lead_time_days === "number" ? Number(base.lead_time_days) : 30,
        certifications: Array.isArray(base.certifications)
          ? base.certifications
          : ["FCC", "CE", "RoHS"],
        category: typeof base.category === "string" ? base.category : undefined,
        extra_prompt: followUp
          ? `追问：${followUp}`
          : typeof base.extra_prompt === "string"
            ? base.extra_prompt
            : "",
      },
      quick,
    );
  };

  const saveCurrentRun = () => {
    if (!result) return;
    saveBatchRun({
      id: makeId(),
      label: result.keyword ?? keyword,
      createdAt: new Date().toISOString(),
      items: [
        {
          label: result.keyword ?? keyword,
          verdict: displayVerdict,
          score: displayScore,
          result: result as unknown as Record<string, unknown>,
        },
      ],
    });
  };

  const displayScore = result?.score ?? result?.arbitration?.score;
  const displayVerdict = result?.verdict ?? result?.arbitration?.verdict;
  const displaySummary =
    result?.summary ??
    (result?.arbitration
      ? `最终建议：${result.arbitration.verdict ?? "谨慎"}；综合得分 ${result.arbitration.score ?? "--"} / 100。`
      : undefined);
  const displayDimensions = result?.dimensions
    ? result.dimensions
    : result?.brains
      ? {
          market: {
            label: result.brains.market?.name ?? "市场分析师",
            score: result.brains.market?.score ?? 0,
            note: result.brains.market?.direction ?? "待分析",
          },
          sentiment: {
            label: result.brains.sentiment?.name ?? "舆情洞察官",
            score: result.brains.sentiment?.score ?? 0,
            note: result.brains.sentiment?.direction ?? "待分析",
          },
          supply_chain: {
            label: result.brains.supply_chain?.name ?? "供应链评估师",
            score: result.brains.supply_chain?.score ?? 0,
            note: result.brains.supply_chain?.direction ?? "待分析",
          },
          finance: {
            label: result.brains.finance?.name ?? "财务精算师",
            score: result.brains.finance?.score ?? 0,
            note: result.brains.finance?.direction ?? "待分析",
          },
        }
      : undefined;
  const proxyEvidence = result?.real_evidence?.proxy;

  return (
    <div className="grid gap-4 lg:grid-cols-[380px_1fr]">
      <GlassCard title="分析输入" description="多提示词个性化输入 + 离线/在线双模式" className="h-fit">
        <div className="grid gap-4">
          <Field label="选品关键词">
            <input
              value={keyword}
              onChange={(event) => handleKeywordChange(event.target.value)}
              className="glass-inset focus-ring h-10 w-full px-3 text-sm"
            />
          </Field>
          <Field label="目标市场">
            <Select
              value={market}
              onValueChange={setMarket}
              options={[
                { value: "us", label: "美国" },
                { value: "eu", label: "欧洲" },
                { value: "sea", label: "东南亚" },
                { value: "jp", label: "日本" },
                { value: "uk", label: "英国" },
              ]}
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="目标售价 USD">
              <NumberInput value={price} onChange={setPrice} />
            </Field>
            <Field label="启动预算 CNY">
              <NumberInput value={budget} onChange={setBudget} step={1000} />
            </Field>
          </div>
          <Field label="目标毛利率 %">
            <NumberInput value={targetMargin} onChange={setTargetMargin} step={0.5} />
          </Field>
          {fourBrainExamples.length > 0 && (
            <div className="grid grid-cols-[1fr_auto] gap-2">
              <Select
                value={exampleId}
                onValueChange={(value) => void applyExample(value)}
                options={exampleOptions}
                ariaLabel="选择四脑示例"
              />
              <Button variant="outline" onClick={() => void applyExample(exampleId)}>
                <Wand2 className="h-4 w-4" />
                填充示例
              </Button>
            </div>
          )}
          <label className="grid gap-1.5">
            <span className="text-xs font-semibold text-slate-400">
              上传用户数据（CSV / JSON）
            </span>
            <input
              type="file"
              accept=".csv,.json"
              onChange={handleFile}
              className="glass-inset focus-ring w-full px-3 py-2 text-xs text-slate-300 file:mr-3 file:rounded-lg file:border-0 file:bg-cyan-400/15 file:px-3 file:py-1.5 file:text-accent"
            />
            {fileName && (
              <Badge tone="cyan">
                <Upload className="h-3.5 w-3.5" />
                {fileName}
              </Badge>
            )}
          </label>
          <Button onClick={() => void run()} disabled={loading} className="w-full">
            <Play className="h-4 w-4" />
            {loading ? "分析中..." : "开始四脑分析"}
          </Button>
        </div>
      </GlassCard>

      <div className="grid gap-4">
        <PageTurnTabs
          defaultValue="market"
          listClassName="w-full justify-start overflow-x-auto"
          tabs={(Object.keys(rolePrompts) as Array<keyof typeof rolePrompts>).map(
            (key) => {
              const conclusion = brainConclusion(result, key);
              return {
                value: key,
                label: roleLabels[key],
                content: (
                  <GlassCard className="p-4">
                    <label className="grid gap-2">
                      <span className="text-xs font-semibold text-slate-400">
                        角色提示词
                      </span>
                      <textarea
                        value={prompts[key]}
                        onChange={(event) =>
                          setPrompts((prev) => ({
                            ...prev,
                            [key]: event.target.value,
                          }))
                        }
                        rows={4}
                        className="glass-inset focus-ring w-full resize-y px-3 py-2.5 text-sm leading-6 text-slate-200"
                      />
                    </label>
                    {conclusion && (
                      <div className="glass-soft mt-3 p-3">
                        <p className="text-xs font-semibold text-slate-300">简洁结论</p>
                        <p className="mt-1 text-sm leading-5 text-slate-200">
                          {conclusion.summary}
                        </p>
                        {conclusion.points.length > 0 && (
                          <ul className="mt-2 grid gap-1">
                            {conclusion.points.map((point, index) => (
                              <li
                                key={index}
                                className="text-[11px] leading-4 text-slate-400"
                              >
                                {point}
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    )}
                  </GlassCard>
                ),
              };
            },
          )}
        />

        <GlassCard title="四脑综合结论" strong>
          {error && (
            <div className="rounded-lg border border-red-300/20 bg-red-500/10 p-3 text-sm text-red-200">
              {error}
            </div>
          )}
          {!result && !loading && (
            <div className="flex min-h-40 flex-col items-center justify-center gap-2 text-center">
              <BrainCircuit className="h-8 w-8 text-accent/60" />
              <p className="text-sm text-slate-400">填写输入后点击“开始四脑分析”</p>
            </div>
          )}
          {loading && (
            <div className="flex min-h-40 items-center justify-center">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent/30 border-t-cyan-300" />
            </div>
          )}
          {result && !loading && (
            <div className="grid gap-4">
              <div className="flex flex-wrap items-center gap-3">
                <Badge tone={displayVerdict?.toLowerCase().includes("go") ? "green" : "amber"}>
                  {displayVerdict ?? "conditional"}
                </Badge>
                <span className="tabular text-xl font-extrabold text-white">
                  {displayScore?.toFixed(0)} / 100
                </span>
                {result.category_name && (
                  <span className="text-xs text-slate-400">{result.category_name}</span>
                )}
                {result.generated_at && (
                  <span className="font-mono text-[10px] text-slate-500">{result.generated_at}</span>
                )}
              </div>
              {displaySummary && (
                <p className="text-sm leading-6 text-slate-300">{displaySummary}</p>
              )}
              <div className="grid gap-3 sm:grid-cols-[1fr_auto]">
                <input
                  value={followUp}
                  onChange={(event) => setFollowUp(event.target.value)}
                  placeholder="输入追问，例如：这款产品的退货风险如何？"
                  className="glass-inset focus-ring h-10 w-full px-3 text-sm"
                />
                <Button variant="secondary" onClick={() => void run()} disabled={loading}>
                  <MessageSquarePlus className="h-4 w-4" />
                  继续追问
                </Button>
              </div>
              <div className="flex justify-end">
                <Button variant="ghost" size="sm" onClick={saveCurrentRun}>
                  <Save className="h-3.5 w-3.5" />
                  保存本次分析
                </Button>
              </div>
              {displayDimensions && (
                <div className="grid gap-3 sm:grid-cols-2">
                  {Object.values(displayDimensions).map((item) => (
                    <div key={item.label} className="glass-soft p-3">
                      <div className="flex items-center justify-between gap-2 text-xs">
                        <span className="font-semibold text-slate-300">{item.label}</span>
                        <span className="tabular text-accent">{item.score}</span>
                      </div>
                      <Progress value={item.score} className="mt-2" />
                      <p className="mt-2 text-[11px] leading-4 text-slate-500">{item.note}</p>
                    </div>
                  ))}
                </div>
              )}
              {proxyEvidence && (
                <div className="glass-inset p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-semibold text-slate-300">真实证据接入</span>
                    <Badge
                      tone={
                        proxyEvidence.available && proxyEvidence.score && proxyEvidence.score >= 70
                          ? "green"
                          : "amber"
                      }
                    >
                      {proxyEvidence.available ? proxyEvidence.level ?? "已接入" : "模型未训练"}
                    </Badge>
                    {proxyEvidence.score != null && (
                      <span className="tabular text-xs text-accent">
                        {proxyEvidence.score.toFixed(1)} / 100
                      </span>
                    )}
                  </div>
                  <p className="mt-2 text-[11px] leading-5 text-slate-400">
                    {proxyEvidence.available
                      ? proxyEvidence.note
                      : "当前组合暂无真实销量代理证据，建议先运行 scripts/train_real_enhanced.py 重训。"}
                  </p>
                  {result.real_evidence?.training_status?.status === "ok" && (
                    <p className="mt-1 text-[10px] text-emerald-300/80">
                      真实特征训练已就绪：{String(result.real_evidence.training_status.combos ?? "")} 组合
                    </p>
                  )}
                </div>
              )}
              {result.research && (
                <div className="glass-inset p-3 text-xs text-slate-400">
                  <div className="flex flex-wrap items-center gap-2">
                    <span>
                      {result.research.disabled
                        ? "本次未联网检索，结论基于内置快照。"
                        : result.research.summary}
                    </span>
                    {!result.research.disabled &&
                      typeof result.research.mock_count === "number" &&
                      result.research.mock_count > 0 && (
                        <Badge tone="amber">模拟 {result.research.mock_count} 条</Badge>
                      )}
                  </div>
                </div>
              )}
              {Array.isArray(result.research?.sources) &&
                (result.research.sources as Array<Record<string, unknown>>).length > 0 && (
                  <div className="glass-inset p-3">
                    <p className="mb-2 text-xs font-semibold text-slate-300">证据来源</p>
                    <div className="grid gap-1.5">
                      {(result.research.sources as Array<Record<string, unknown>>).slice(0, 6).map(
                        (source, index) => (
                          <div key={index} className="flex items-center gap-2">
                            <a
                              href={String(source.link ?? "#")}
                              target="_blank"
                              rel="noreferrer"
                              className="truncate text-xs text-accent hover:underline"
                            >
                              {String(source.title ?? source.link ?? "--")}
                            </a>
                            {isMockSource(source) && <Badge tone="amber">模拟</Badge>}
                          </div>
                        ),
                      )}
                    </div>
                  </div>
                )}
              {result.charts && result.charts.length > 0 && (
                <div className="grid gap-4">
                  {result.charts.map((chart) => (
                    <div key={chart.id ?? chart.type} className="glass-soft p-3">
                      <p className="mb-2 text-xs font-semibold text-slate-300">
                        {chart.title ?? chart.type}
                      </p>
                      <AppChart option={toEChartsOption(chart)} height={260} />
                    </div>
                  ))}
                </div>
              )}
              {result.report && (
                <div className="glass-soft p-4">
                  <MarkdownView content={result.report} />
                </div>
              )}
            </div>
          )}
        </GlassCard>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="grid gap-1.5">
      <span className="text-xs font-semibold text-slate-400">{label}</span>
      {children}
    </label>
  );
}

function NumberInput({
  value,
  onChange,
  step = 1,
}: {
  value: number;
  onChange: (value: number) => void;
  step?: number;
}) {
  return (
    <input
      type="number"
      value={value}
      step={step}
      onChange={(event) => onChange(Number(event.target.value))}
      className="glass-inset focus-ring h-10 w-full px-3 text-sm"
    />
  );
}

function brainConclusion(
  result: FourBrainResult | null,
  key: keyof typeof rolePrompts,
): { summary: string; points: string[] } | null {
  const brain = result?.brains?.[key];
  if (!brain) return null;
  const points = Array.isArray(brain.conclusion_points)
    ? brain.conclusion_points
        .map((point) => String(point).trim())
        .filter(Boolean)
    : [
        ...pointStrings(brain.opportunities),
        ...pointStrings(brain.risks),
        ...(brain.evidence ?? []),
      ].slice(0, 3);
  return {
    summary: brain.ai_summary || brain.summary || brain.direction || "--",
    points,
  };
}

function pointStrings(items?: unknown[]): string[] {
  return (items ?? [])
    .map((item) => {
      if (typeof item === "string") return item;
      if (item && typeof item === "object") {
        const candidate = item as Record<string, unknown>;
        const value = candidate.idea ?? candidate.issue;
        if (typeof value === "string") return value;
      }
      return String(item);
    })
    .map((item) => item.trim())
    .filter(Boolean);
}

function makeId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function toEChartsOption(
  chart: {
    id?: string;
    type?: string;
    title?: string;
    labels?: string[] | Record<string, unknown>;
    series?: Array<{ name?: string; values?: number[] }>;
    values?: number[][];
  },
): EChartsOption {
  const labels = Array.isArray(chart.labels) ? (chart.labels as string[]) : [];
  const series = chart.series ?? [];
  if (chart.type === "radar") {
    return {
      radar: {
        indicator: labels.map((label) => ({ name: label, max: 100 })),
      },
      series: [
        {
          type: "radar",
          data: [
            {
              value: series[0]?.values ?? [],
              name: series[0]?.name ?? "评分",
            },
          ],
        },
      ],
    } as EChartsOption;
  }
  if (chart.type === "bar") {
    return {
      tooltip: { trigger: "axis" },
      xAxis: { type: "category", data: labels },
      yAxis: { type: "value" },
      series: series.map((item) => ({
        type: "bar",
        name: item.name,
        data: item.values ?? [],
      })),
    } as EChartsOption;
  }
  if (chart.type === "line") {
    return {
      tooltip: { trigger: "axis" },
      xAxis: { type: "category", data: labels },
      yAxis: { type: "value" },
      series: series.map((item) => ({
        type: "line",
        smooth: true,
        name: item.name,
        data: item.values ?? [],
      })),
    } as EChartsOption;
  }
  if (chart.type === "heatmap") {
    const rowLabels =
      typeof chart.labels === "object" && !Array.isArray(chart.labels)
        ? ((chart.labels as Record<string, unknown>).rows as string[]) ?? []
        : [];
    const colLabels =
      typeof chart.labels === "object" && !Array.isArray(chart.labels)
        ? ((chart.labels as Record<string, unknown>).cols as string[]) ?? []
        : [];
    const cells: Array<[number, number, number]> = [];
    (chart.values ?? []).forEach((rowValues, rowIndex) => {
      rowValues.forEach((value, colIndex) => {
        cells.push([colIndex, rowIndex, value]);
      });
    });
    return {
      tooltip: { position: "top" },
      grid: { left: 120, right: 40, top: 40, bottom: 80 },
      xAxis: { type: "category", data: colLabels, splitArea: { show: true } },
      yAxis: { type: "category", data: rowLabels, splitArea: { show: true } },
      visualMap: { min: 0, max: 100, calculable: true, orient: "horizontal", left: "center", bottom: 0 },
      series: [{ type: "heatmap", data: cells, label: { show: false } }],
    } as EChartsOption;
  }
  return {};
}

export function isMockSource(source: Record<string, unknown>): boolean {
  const sourceName = String(source.source ?? "").toLowerCase();
  const title = String(source.title ?? "");
  return sourceName === "mock" || title.startsWith("Mock result");
}
