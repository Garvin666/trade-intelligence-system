import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  Calculator,
  CircleDollarSign,
  FileCheck2,
  Gauge,
  Layers,
  Ship,
  Sparkles,
  TriangleAlert,
  Wand2,
} from "lucide-react";
import {
  fetchTradeDecision,
  postTradeAnalyze,
  postTradeAutofill,
} from "@/shared/api/client";
import { useAiConfig, useTradeCatalog } from "@/shared/api/hooks";
import { IS_OFFLINE } from "@/shared/api/offline";
import type { TradeDecision } from "@/shared/api/types";
import {
  categoryName,
  fallbackCategoryOptions,
  fallbackMarketOptions,
  marketName,
} from "@/shared/lib/names";
import {
  computeDecisionScore,
  STRATEGY_LABELS,
  TRADE_PRESETS,
  type TradeStrategy,
} from "@/shared/lib/tradeVerdict";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { GlassCard } from "@/shared/ui/glass-card";
import { Select } from "@/shared/ui/select";
import { useTradeIntelStore } from "@/shared/store/trade-intel";
import { TradeResultDetail } from "./TradeResultDetail";
import { TradeScenarioSandbox } from "./TradeScenarioSandbox";
import { VerdictBanner } from "./VerdictBanner";

const strategyOptions = (Object.keys(STRATEGY_LABELS) as TradeStrategy[]).map((value) => ({
  value,
  label: STRATEGY_LABELS[value],
}));

interface TradeAiResult {
  data?: {
    title?: string;
    summary?: string;
    confidence?: number;
    signals?: unknown[];
    actions?: unknown[];
  };
  ai_used?: boolean;
  mode?: string;
  reason?: string;
  research?: {
    summary?: string;
    provider?: string;
    fallback_used?: boolean;
    sources?: unknown[];
  };
}

export function TradeDecisionPanel() {
  const { data: aiConfig } = useAiConfig();
  const { data: catalog } = useTradeCatalog();
  const selectionDraft = useTradeIntelStore((state) => state.selectionDraft);
  const setSelectionDraft = useTradeIntelStore((state) => state.setSelectionDraft);
  const [category, setCategory] = useState(
    String(selectionDraft?.category ?? "cn_latiao"),
  );
  const [market, setMarket] = useState(String(selectionDraft?.market ?? "us"));
  const [price, setPrice] = useState(
    typeof selectionDraft?.price === "number" ? Number(selectionDraft.price) : 32.9,
  );
  const [cost, setCost] = useState(
    typeof selectionDraft?.procurement_cost_cny === "number"
      ? Number(selectionDraft.procurement_cost_cny)
      : 88,
  );
  const [productName, setProductName] = useState(
    String(selectionDraft?.keyword ?? "辣条（网红休闲零食）"),
  );
  const [strategy, setStrategy] = useState<TradeStrategy>("balanced");
  const [presetId, setPresetId] = useState("");
  const [loading, setLoading] = useState(false);
  const [autoFillLoading, setAutoFillLoading] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [result, setResult] = useState<TradeDecision | null>(null);
  const [aiResult, setAiResult] = useState<TradeAiResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [aiError, setAiError] = useState<string | null>(null);
  const autoRunRef = useRef(false);

  const applyPreset = () => {
    const preset = TRADE_PRESETS.find((item) => item.id === presetId);
    if (!preset) return;
    setCategory(preset.category);
    setMarket(preset.market);
    setPrice(preset.price);
    setCost(preset.cost);
    setProductName(categoryName(preset.category));
    setStrategy(preset.strategy);
    setResult(null);
    setError(null);
  };

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchTradeDecision({
        category,
        market,
        unit_price_usd: price,
        procurement_cost_cny: cost,
        product_name: productName,
      });
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "贸易决策计算失败。");
    } finally {
      setLoading(false);
    }
  };

  // 市场择优卡片跨页签草稿：挂载时填充输入后自动出结果
  useEffect(() => {
    if (selectionDraft?.fromMarketCard && !autoRunRef.current) {
      autoRunRef.current = true;
      void run();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectionDraft]);

  useEffect(() => {
    if (selectionDraft) setSelectionDraft(null);
  }, [selectionDraft, setSelectionDraft]);

  const categoryOptions = useMemo(() => {
    const items = catalog?.data?.categories ?? [];
    if (items.length) {
      return items
        .filter((item) => item.key)
        .map((item) => ({ value: item.key, label: String(item.label ?? categoryName(item.key)) }));
    }
    return fallbackCategoryOptions;
  }, [catalog]);

  const marketOptions = useMemo(() => {
    const items = catalog?.data?.markets ?? [];
    if (items.length) {
      return items
        .filter((item) => item.key)
        .map((item) => ({ value: item.key, label: String(item.label ?? marketName(item.key)) }));
    }
    return fallbackMarketOptions;
  }, [catalog]);

  const autofill = async () => {
    setAutoFillLoading(true);
    setError(null);
    try {
      const payload = await postTradeAutofill({
        profile: {
          productKeyword: productName,
          budget: cost * 400,
          businessStage: "test",
          stockPreference: "light",
        },
        current: { category, market, customCategory: productName },
      });
      const input = (payload.data?.input ?? {}) as Record<string, unknown>;
      if (input.category) setCategory(String(input.category));
      if (input.market) setMarket(String(input.market));
      if (input.customCategory) setProductName(String(input.customCategory));
      if (typeof input.price === "number") setPrice(input.price);
      if (typeof input.cost === "number") setCost(input.cost);
    } catch (err) {
      setError(err instanceof Error ? err.message : "自动填充失败");
    } finally {
      setAutoFillLoading(false);
    }
  };

  const riskTone = result?.risk_level === "low" ? "green" : result?.risk_level === "medium" ? "amber" : "red";
  const verdict = useMemo(
    () => (result ? computeDecisionScore(result, { strategy }) : null),
    [result, strategy],
  );

  const runAiAnalysis = async () => {
    if (IS_OFFLINE) {
      setAiError("离线模式不提供 AI 解读，请在在线后端中运行。");
      return;
    }
    setAiLoading(true);
    setAiError(null);
    try {
      const fxRate =
        typeof catalog?.fx_rate === "number" && catalog.fx_rate > 0
          ? catalog.fx_rate
          : 7.15;
      const payload = {
        scenario: {
          input: {
            category,
            customCategory: productName,
            market,
            platform: "amazon",
            route: "air",
            quantity: 300,
            price,
            cost: Math.round((cost / fxRate) * 100) / 100,
            weight: 0.58,
            freight: 3.4,
            adRate: 0.12,
            tariff: 0.08,
            returnRate: 0.03,
            fxRisk: 0.02,
            paymentDays: 30,
            inventoryDays: 45,
          },
          profile: {
            productKeyword: productName,
            customerSegment: "mass",
            businessStage: "test",
            goal: "growth",
            riskTolerance: "medium",
            budget: cost * 400,
            stockPreference: "light",
          },
          result: {
            decisionScore: verdict?.score ?? 0,
            margin: Number(result?.margin_pct ?? 0),
            riskScore: verdict?.components.risk ?? 0,
            cashDays: verdict?.cashDays ?? 75,
            profileFit: verdict?.components.financing ?? 0,
          },
        },
        catalog: {
          category: { key: category, label: categoryName(category) },
          market: { key: market, label: marketName(market) },
          platform: { key: "amazon", label: "Amazon" },
          route: { key: "air", label: "空运快反" },
        },
        research: true,
        lang: "zh",
      };
      const response = (await postTradeAnalyze(payload)) as TradeAiResult;
      setAiResult(response);
    } catch (err) {
      setAiError(err instanceof Error ? err.message : "AI 分析失败");
    } finally {
      setAiLoading(false);
    }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
      <GlassCard title="方案参数" description="品类 × 市场 × 成本输入" className="h-fit">
        <div className="grid gap-4">
          <Field label="商品品类">
            <Select value={category} onValueChange={setCategory} options={categoryOptions} />
          </Field>
          <Field label="目标市场">
            <Select value={market} onValueChange={setMarket} options={marketOptions} />
          </Field>
          <Field label="产品名称">
            <input
              value={productName}
              onChange={(event) => setProductName(event.target.value)}
              className="glass-inset focus-ring h-10 w-full px-3 text-sm"
            />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="售价 USD">
              <NumberInput value={price} onChange={setPrice} step={0.1} />
            </Field>
            <Field label="采购成本 CNY">
              <NumberInput value={cost} onChange={setCost} step={1} />
            </Field>
          </div>

          <Field label="决策策略">
            <Select value={strategy} onValueChange={(value) => setStrategy(value as TradeStrategy)} options={strategyOptions} />
          </Field>

          <div className="grid gap-2">
            <Field label="方案预设">
              <div className="grid grid-cols-[1fr_auto] gap-2">
                <Select
                  value={presetId}
                  onValueChange={setPresetId}
                  options={TRADE_PRESETS.map((preset) => ({ value: preset.id, label: preset.label }))}
                  placeholder="选择方案预设"
                  ariaLabel="选择方案预设"
                />
                <Button variant="outline" onClick={applyPreset} disabled={!presetId}>
                  <Layers className="h-4 w-4" />
                  应用
                </Button>
              </div>
            </Field>
            <p className="text-[11px] leading-4 text-slate-500">
              预设含策略：东南亚辣条试单 / 美国辣椒酱增长 / 欧洲绿茶利润 / 低风险小批快反
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Button variant="secondary" onClick={autofill} disabled={autoFillLoading}>
              <Wand2 className="h-4 w-4" />
              {autoFillLoading ? "填充中..." : "自动填充"}
            </Button>
            <Button onClick={run} disabled={loading}>
              <Calculator className="h-4 w-4" />
              {loading ? "测算中..." : "生成决策"}
            </Button>
          </div>
        </div>
      </GlassCard>

      <div className="grid gap-4">
        {error && (
          <div className="glass rounded-lg border-red-300/20 bg-red-500/10 p-3 text-sm text-red-200">
            {error}
          </div>
        )}
        {!result && !loading && (
          <GlassCard title="决策结果" className="flex min-h-64 items-center justify-center">
            <div className="text-center">
              <CircleDollarSign className="mx-auto h-10 w-10 text-accent/60" />
              <p className="mt-3 text-sm text-slate-400">输入方案参数后生成完整贸易决策报告</p>
            </div>
          </GlassCard>
        )}
        {loading && (
          <GlassCard title="决策结果" className="flex min-h-64 items-center justify-center">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-accent/30 border-t-cyan-300" />
          </GlassCard>
        )}
        {result && !loading && (
          <>
            {verdict && <VerdictBanner verdict={verdict} />}
            <AiInsightCard
              configured={Boolean(aiConfig?.configured)}
              loading={aiLoading}
              result={aiResult}
              error={aiError}
              onRun={runAiAnalysis}
            />
            <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
              <Metric
                label="毛利率"
                value={`${result.margin_pct?.toFixed(1)}%`}
                tone={result.margin_pct >= 20 ? "green" : "red"}
              />
              <Metric
                label="有效关税"
                value={`${(result.effective_tariff_rate * 100).toFixed(0)}%`}
                tone="amber"
              />
              <Metric label="可行性评分" value={`${result.feasibility_score ?? 0}`} tone="cyan" />
              <Metric label="HS Code" value={result.hs_code ?? "--"} tone="cyan" mono />
            </div>
            <GlassCard title="核心结论">
              <div className="mb-4 flex flex-wrap items-center gap-3">
                <Badge tone={riskTone}>{result.risk_level ?? "medium"}</Badge>
                <span className="text-sm text-slate-400">
                  {String(result.risk_message ?? "")}
                </span>
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                <InfoRow
                  icon={FileCheck2}
                  label="合规建议"
                  value={String(result.compliance_recommendation ?? "--")}
                />
                <InfoRow icon={Ship} label="最优物流" value={String(result.best_logistics ?? "--")} />
                <InfoRow
                  icon={TriangleAlert}
                  label="政策动作"
                  value={
                    Array.isArray(result.policy_actions)
                      ? (result.policy_actions as unknown[]).map(String).join(" / ")
                      : "--"
                  }
                />
                <InfoRow
                  icon={CircleDollarSign}
                  label="到岸成本"
                  value={
                    typeof result.best_landed_cost_usd === "number"
                      ? `$${result.best_landed_cost_usd.toFixed(2)}`
                      : "--"
                  }
                />
              </div>
            </GlassCard>
            <EvidenceStrip result={result} />
            <TradeResultDetail result={result} />
            <TradeScenarioSandbox result={result} category={category} market={market} strategy={strategy} />
          </>
        )}
      </div>
    </div>
  );
}

/** 数据口径标注：证据闸 + mock 标注意识（报告强调的优势） */
function EvidenceStrip({ result }: { result: TradeDecision }) {
  const sourceQuality = String(result.source_quality ?? "demo");
  const sourceVerified = sourceQuality === "verified" || sourceQuality === "official";
  const hsVerified = result.hs_verified === true;
  const clamped = result.clamped === true || result.margin_clamped === true;
  const warnings = Array.isArray(result.warnings) ? (result.warnings as unknown[]) : [];
  return (
    <div className="glass rounded-lg p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-400">
          <Gauge className="h-3.5 w-3.5 text-accent" />
          数据口径
        </span>
        <Badge tone={sourceVerified ? "green" : "amber"}>
          政策来源：{sourceVerified ? "官方已核验" : sourceQuality}
        </Badge>
        <Badge tone={hsVerified ? "green" : "amber"}>
          HS {hsVerified ? "已核实" : "待核实"}
        </Badge>
        {clamped && <Badge tone="red">利润率已钳制</Badge>}
        <Badge tone="neutral">演示参数可替换</Badge>
      </div>
      {warnings.length > 0 && (
        <div className="mt-2 grid gap-1 text-[11px] text-slate-500">
          {(warnings as unknown[]).map((warning, index) => (
            <p key={index}>- {String(warning)}</p>
          ))}
        </div>
      )}
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
  step,
}: {
  value: number;
  onChange: (value: number) => void;
  step: number;
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

function Metric({
  label,
  value,
  tone,
  mono = false,
}: {
  label: string;
  value: string;
  tone: "green" | "red" | "amber" | "cyan";
  mono?: boolean;
}) {
  const color = {
    green: "text-emerald-300",
    red: "text-red-300",
    amber: "text-amber-300",
    cyan: "text-accent",
  }[tone];
  return (
    <GlassCard className="p-4">
      <p className="text-xs font-semibold text-slate-400">{label}</p>
      <p className={`tabular mt-1 text-xl font-extrabold ${mono ? "font-mono" : ""} ${color}`}>
        {value}
      </p>
    </GlassCard>
  );
}

function InfoRow({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Ship;
  label: string;
  value?: string;
}) {
  return (
    <div className="glass-soft flex items-start gap-3 p-3">
      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
      <div className="min-w-0">
        <p className="text-[11px] font-semibold text-slate-500">{label}</p>
        <p className="mt-0.5 text-sm text-slate-200">{value || "--"}</p>
      </div>
    </div>
  );
}

function AiInsightCard({
  configured,
  loading,
  result,
  error,
  onRun,
}: {
  configured: boolean;
  loading: boolean;
  result: TradeAiResult | null;
  error: string | null;
  onRun: () => void;
}) {
  const aiUsed = result?.ai_used === true;
  const research = result?.research;
  const researchCount = Array.isArray(research?.sources) ? research.sources.length : 0;
  const data = result?.data;

  return (
    <GlassCard
      title="AI 决策解读"
      description="由顶部 AI 接入配置的大模型对本方案做综合解读，联网研究来源随结果标注"
      strong
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Badge tone={aiUsed ? "green" : result ? "neutral" : "neutral"}>
          <Sparkles className="h-3.5 w-3.5" />
          {aiUsed ? "AI 已接入" : result ? "本地规则引擎回退" : "尚未运行"}
        </Badge>
        <Badge tone={configured ? "cyan" : "amber"}>
          {configured ? "模型已配置" : "顶部 AI 接入未配置"}
        </Badge>
        {researchCount > 0 && <Badge tone="neutral">{researchCount} 条联网来源</Badge>}
      </div>

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          {loading && <p className="text-sm text-slate-400">AI 正在结合联网研究生成解读…</p>}
          {!loading && !result && (
            <p className="text-sm text-slate-400">
              {configured
                ? "基于当前方案数据与联网研究，生成大模型综合决策解读。"
                : "需先在顶部「AI 接入」填写 API Key 与模型并保存配置。"}
            </p>
          )}
          {!loading && result && data && (
            <div className="grid gap-3">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-base font-bold text-white">{data.title ?? "AI 综合解读"}</p>
                {typeof data.confidence === "number" && (
                  <Badge tone="cyan">置信度 {data.confidence}%</Badge>
                )}
              </div>
              <p className="text-sm leading-6 text-slate-300">{data.summary ?? ""}</p>
              {Array.isArray(data.signals) && data.signals.length > 0 && (
                <div className="grid gap-1.5">
                  <p className="text-[11px] font-semibold text-slate-500">关键判断</p>
                  {(data.signals as unknown[]).map((signal, index) => (
                    <p key={index} className="flex items-start gap-2 text-xs text-slate-300">
                      <Sparkles className="mt-0.5 h-3 w-3 text-accent" />
                      {String(signal)}
                    </p>
                  ))}
                </div>
              )}
              {Array.isArray(data.actions) && data.actions.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {(data.actions as unknown[]).map((action, index) => (
                    <Badge key={index} tone="amber">
                      {String(action)}
                    </Badge>
                  ))}
                </div>
              )}
              {research && (
                <div className="glass-inset p-3 text-xs text-slate-400">
                  <p className="font-semibold text-slate-300">
                    {research.summary ?? `已检索 ${researchCount} 条来源`}
                  </p>
                  {research.provider && (
                    <p className="mt-1 text-[11px] text-slate-500">
                      搜索源：{research.provider}
                      {research.fallback_used ? "（含回退）" : ""}
                    </p>
                  )}
                </div>
              )}
            </div>
          )}
          {!loading && result && !data && (
            <p className="text-sm text-slate-400">AI 未返回可展示内容。</p>
          )}
        </div>
        <Button
          variant="secondary"
          size="sm"
          onClick={onRun}
          disabled={loading || !configured}
          title={configured ? "运行 AI 解读" : "请先在顶部 AI 接入中保存配置"}
        >
          <Sparkles className="h-3.5 w-3.5" />
          {loading ? "解读中..." : result ? "重新解读" : "运行 AI 解读"}
        </Button>
      </div>

      {!loading && error && <p className="mt-3 text-xs text-red-300">{error}</p>}
      {!loading && result?.ai_used === false && result.reason && (
        <p className="mt-2 text-[11px] text-slate-500">回退原因：{result.reason}</p>
      )}
    </GlassCard>
  );
}
