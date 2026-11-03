import type { TradeDecision } from "@/shared/api/types";
import { calculateTradeScenario, type TradeScenarioResult } from "./tradeScenario";

/**
 * 贸易决策评分库（演示口径）。
 *
 * 移植自解析报告《四脑工作台与贸易决策Demo》所述的独立贸易决策工作台：
 * - 四维分量（需求 / 利润 / 现金 / 风险）× 四套策略权重 → 决策分 decisionScore；
 * - 决策状态 getDecisionStatus：≥74 且毛利≥12% 且风险非高且现金≤105 天 → 建议进入；
 *   ≥62 → 小批试单；否则 → 暂缓进入。
 * 纯函数、无网络依赖，供决策横幅 / 经营沙盘 / 市场择优 / 压力测试 / 平台适配共用。
 */

export type TradeStrategy = "balanced" | "growth" | "profit" | "risk";

export interface StrategyWeights {
  demand: number;
  profit: number;
  cash: number;
  risk: number;
}

export const STRATEGIES: Record<TradeStrategy, StrategyWeights> = {
  balanced: { demand: 0.25, profit: 0.3, cash: 0.15, risk: 0.3 },
  growth: { demand: 0.35, profit: 0.2, cash: 0.15, risk: 0.3 },
  profit: { demand: 0.2, profit: 0.4, cash: 0.1, risk: 0.3 },
  risk: { demand: 0.15, profit: 0.2, cash: 0.2, risk: 0.45 },
};

export const STRATEGY_LABELS: Record<TradeStrategy, string> = {
  balanced: "均衡",
  growth: "增长",
  profit: "利润",
  risk: "稳健",
};

export type Verdict = "enter" | "trial" | "hold";

export const VERDICT_LABELS: Record<Verdict, string> = {
  enter: "建议进入",
  trial: "小批试单",
  hold: "暂缓进入",
};

export interface DecisionComponents {
  demand: number;
  profit: number;
  cash: number;
  risk: number;
  feasibility: number;
  financing: number;
}

export interface VerdictResult {
  score: number;
  verdict: Verdict;
  verdictLabel: string;
  reasons: string[];
  components: DecisionComponents;
  strategy: TradeStrategy;
  /** 基于当前策略计算出的现金周期（天） */
  cashDays: number;
}

export interface VerdictOptions {
  strategy?: TradeStrategy;
  /** 市场对比行（avg_sales_volume / avg_competition_index），用于需求分量 */
  marketCompareRow?: Record<string, unknown> | null;
  /** 沙盘测算结果：提供时利润/现金分量以其为准（压力测试与动作差值用） */
  scenario?: TradeScenarioResult;
  /** 显式现金周期（天）覆盖，默认库存 45 天 + 账期 30 天 */
  cashDays?: number;
}

const DEFAULT_CASH_DAYS = 75; // 45 库存 + 30 账期（演示假设）

/** 贸易方案预设（移植报告所述 4 套方案预设） */
export interface TradePreset {
  id: string;
  label: string;
  description: string;
  category: string;
  market: string;
  price: number;
  cost: number;
  strategy: TradeStrategy;
}

export const TRADE_PRESETS: TradePreset[] = [
  {
    id: "preset_sea_latiao",
    label: "东南亚辣条试单",
    description: "低门槛小批量试单，适合初次出海",
    category: "cn_latiao",
    market: "sea",
    price: 4.9,
    cost: 12,
    strategy: "balanced",
  },
  {
    id: "preset_us_laoganma",
    label: "美国辣椒酱增长",
    description: "成熟市场调味品，追求销量增长",
    category: "cn_laoganma",
    market: "us",
    price: 9.9,
    cost: 26,
    strategy: "growth",
  },
  {
    id: "preset_eu_longjing",
    label: "欧洲绿茶利润",
    description: "欧洲茶叶礼盒，主打利润率",
    category: "cn_longjing",
    market: "eu",
    price: 29.9,
    cost: 96,
    strategy: "profit",
  },
  {
    id: "preset_risk_mifen",
    label: "低风险小批快反",
    description: "低风险品类快速反应，稳健优先",
    category: "cn_changsha_mifen",
    market: "sea",
    price: 12.9,
    cost: 42,
    strategy: "risk",
  },
];

function clamp(value: number, low = 0, high = 100): number {
  return Math.max(low, Math.min(high, value));
}

function round(value: number): number {
  return Math.round(value * 10) / 10;
}

function toNumber(value: unknown, fallback = 0): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

/** 利润分量：毛利率 0–35% 线性映射 0–100，≥35% 满分，≤0 记 0 */
export function scoreProfit(marginPct: number): number {
  return clamp((marginPct / 35) * 100);
}

/** 风险分量：按风险等级给基础分，再按物流/冲突裁决微调，低毛利时追加扣分 */
export function scoreRisk(
  payload: TradeDecision,
  scenarioMarginPct?: number,
): number {
  const level = String(payload.risk_level ?? "medium");
  let base = level === "low" ? 90 : level === "high" ? 20 : 60;
  const freight = String(payload.freight_risk ?? "");
  if (freight === "high") base -= 10;
  else if (freight === "medium") base -= 5;
  const conflict = String(payload.conflict_level ?? "");
  if (conflict === "high") base -= 10;
  else if (conflict === "medium") base -= 5;
  if (typeof scenarioMarginPct === "number" && scenarioMarginPct < 12) {
    // 场景毛利跌破 12% 时每 1 个点扣 3 分（封顶 30），让成本冲击真实反映到风险
    base -= Math.min(30, (12 - scenarioMarginPct) * 3);
  }
  return clamp(base);
}

/** 现金分量：现金周期越短越优 */
export function scoreCash(cashDays: number): number {
  if (cashDays <= 45) return 100;
  if (cashDays <= 90) return 75;
  if (cashDays <= 120) return 50;
  return 30;
}

/** 需求分量：优先用市场对比数据（销量归一化 + 竞争度反向），否则用舆情分代理 */
export function scoreDemand(payload: TradeDecision, marketRow?: Record<string, unknown> | null): number {
  const sales = toNumber(marketRow?.avg_sales_volume, Number.NaN);
  const competition = toNumber(marketRow?.avg_competition_index, Number.NaN);
  if (Number.isFinite(sales) && Number.isFinite(competition)) {
    const salesScore = clamp((sales / 80) * 100);
    const compScore = clamp(100 - competition);
    return round(salesScore * 0.6 + compScore * 0.4);
  }
  const sentiment = toNumber(payload.sentiment_avg_score, Number.NaN);
  if (Number.isFinite(sentiment)) {
    return round(((sentiment + 1) / 2) * 100);
  }
  return 50;
}

/** 综合决策评分与裁决 */
export function computeDecisionScore(
  payload: TradeDecision,
  options: VerdictOptions = {},
): VerdictResult {
  const strategy = options.strategy ?? "balanced";
  const weights = STRATEGIES[strategy];
  const scenario = options.scenario;
  const profitScore = scenario ? scoreProfit(scenario.margin_pct) : scoreProfit(toNumber(payload.margin_pct));
  const cashDays = options.cashDays ?? scenario?.cash_days ?? DEFAULT_CASH_DAYS;
  const cashScore = scoreCash(cashDays);
  const demandScore = scoreDemand(payload, options.marketCompareRow ?? null);
  const riskScore = scoreRisk(payload, scenario?.margin_pct);
  const feasibility = clamp(toNumber(payload.feasibility_score, 50));
  const financing = clamp(toNumber(payload.financing_ready_score, 50));

  const weighted =
    demandScore * weights.demand +
    profitScore * weights.profit +
    cashScore * weights.cash +
    riskScore * weights.risk;
  // 可行性 / 融资就绪以小幅权重并入总分，避免低频分主导裁决
  const score = round(weighted * 0.9 + feasibility * 0.05 + financing * 0.05);

  const marginPct = scenario ? scenario.margin_pct : toNumber(payload.margin_pct);
  const marginOk = marginPct >= 12;
  const riskOk = String(payload.risk_level ?? "medium") !== "high";
  const cashOk = cashDays <= 105;

  const reasons: string[] = [];
  reasons.push(
    `决策分 ${score}（策略：${STRATEGY_LABELS[strategy]}）`,
  );
  reasons.push(
    marginOk
      ? `毛利率 ${marginPct.toFixed(1)}% 达标（≥12%）`
      : `毛利率 ${marginPct.toFixed(1)}% 低于 12% 门槛`,
  );
  reasons.push(
    riskOk
      ? `风险等级 ${String(payload.risk_level ?? "medium")}，可接受`
      : `风险等级 high，需谨慎评估`,
  );
  reasons.push(
    cashOk ? `现金周期 ${cashDays} 天达标（≤105 天）` : `现金周期 ${cashDays} 天超限（>105 天）`,
  );
  if (options.marketCompareRow == null && !Number.isFinite(toNumber(payload.sentiment_avg_score, Number.NaN))) {
    reasons.push("需求分按保守默认值估算（无市场对比与舆情数据）");
  }
  if (feasibility < 55) reasons.push(`准入可行性偏低（${feasibility} 分），关注认证成本与周期`);
  if (financing < 55) reasons.push(`融资就绪偏低（${financing} 分），需预留现金流`);

  let verdict: Verdict;
  if (score >= 74 && marginOk && riskOk && cashOk) {
    verdict = "enter";
  } else if (score >= 62) {
    verdict = "trial";
  } else {
    verdict = "hold";
  }

  return {
    score,
    verdict,
    verdictLabel: VERDICT_LABELS[verdict],
    reasons,
    components: {
      demand: round(demandScore),
      profit: round(profitScore),
      cash: round(cashScore),
      risk: round(riskScore),
      feasibility: round(feasibility),
      financing: round(financing),
    },
    strategy,
    cashDays: Math.round(cashDays),
  };
}

/** 徽章色调映射 */
export function verdictTone(verdict: Verdict): "green" | "amber" | "red" {
  if (verdict === "enter") return "green";
  if (verdict === "trial") return "amber";
  return "red";
}

// ---------------------------------------------------------------------------
// 经营沙盘一键动作（移植报告所述 ACTIONS：提价 / 采购降本 / 广告加码 / 切换空运 / 成本冲击）
// ---------------------------------------------------------------------------

export type TradeActionId =
  | "price_up"
  | "cost_down"
  | "ad_up"
  | "air_route"
  | "cost_shock";

export interface TradeActionMeta {
  id: TradeActionId;
  label: string;
  description: string;
}

export const TRADE_ACTIONS: TradeActionMeta[] = [
  { id: "price_up", label: "提价 3%", description: "售价上调 3%，改善毛利" },
  { id: "cost_down", label: "采购降本 5%", description: "采购成本下调 5%" },
  { id: "ad_up", label: "广告加码 2 点", description: "广告费率 +2 个百分点" },
  { id: "air_route", label: "切换空运", description: "物流改空运，到岸成本约 +15%" },
  { id: "cost_shock", label: "成本冲击 +10%", description: "模拟关税/物流/汇率成本上涨 10%" },
];

export interface TradeSandboxInputs {
  unit_price_usd: number;
  procurement_cost_cny: number;
  quantity: number;
  ad_rate: number;
  return_rate: number;
  inventory_days: number;
  fx_rate: number;
  landed_cost_usd?: number;
  platform_commission_rate?: number;
  payment_days?: number;
}

/** 把一键动作作用于当前沙盘输入，返回新输入（纯函数） */
export function applyTradeAction(
  inputs: TradeSandboxInputs,
  actionId: TradeActionId,
): TradeSandboxInputs {
  const next = { ...inputs };
  switch (actionId) {
    case "price_up":
      next.unit_price_usd = roundNumber(inputs.unit_price_usd * 1.03);
      break;
    case "cost_down":
      next.procurement_cost_cny = roundNumber(inputs.procurement_cost_cny * 0.95);
      break;
    case "ad_up":
      next.ad_rate = roundNumber(inputs.ad_rate + 0.02);
      break;
    case "air_route":
      if (typeof next.landed_cost_usd === "number") {
        next.landed_cost_usd = roundNumber(next.landed_cost_usd * 1.15);
      } else {
        next.procurement_cost_cny = roundNumber(inputs.procurement_cost_cny * 1.15);
      }
      break;
    case "cost_shock":
      next.procurement_cost_cny = roundNumber(inputs.procurement_cost_cny * 1.1);
      if (typeof next.landed_cost_usd === "number") {
        next.landed_cost_usd = roundNumber(next.landed_cost_usd * 1.1);
      }
      break;
  }
  return next;
}

function roundNumber(value: number): number {
  return Math.round(value * 100) / 100;
}

/** 由沙盘输入直接产出完整测算与裁决（沙盘/压力测试/平台排行共用） */
export function buildScenarioVerdict(
  payload: TradeDecision,
  inputs: TradeSandboxInputs,
  options: Omit<VerdictOptions, "scenario"> = {},
): { scenario: TradeScenarioResult; verdict: VerdictResult } {
  const scenario = calculateTradeScenario({
    category: payload.category,
    market: payload.market,
    unit_price_usd: inputs.unit_price_usd,
    procurement_cost_cny: inputs.procurement_cost_cny,
    quantity: inputs.quantity,
    ad_rate: inputs.ad_rate,
    return_rate: inputs.return_rate,
    inventory_days: inputs.inventory_days,
    fx_rate: inputs.fx_rate,
    landed_cost_usd: inputs.landed_cost_usd,
    platform_commission_rate: inputs.platform_commission_rate,
    payment_days: inputs.payment_days,
  });
  const verdict = computeDecisionScore(payload, { ...options, scenario });
  return { scenario, verdict };
}
