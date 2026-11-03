import { describe, expect, it } from "vitest";
import {
  applyTradeAction,
  buildScenarioVerdict,
  computeDecisionScore,
  scoreCash,
  scoreDemand,
  scoreProfit,
  scoreRisk,
  TRADE_ACTIONS,
  TRADE_PRESETS,
} from "@/shared/lib/tradeVerdict";
import type { TradeDecision } from "@/shared/api/types";

function makePayload(overrides: Partial<TradeDecision> = {}): TradeDecision {
  return {
    category: "cn_latiao",
    category_name: "辣条",
    market: "us",
    market_name: "美国",
    unit_price_usd: 39.9,
    procurement_cost_cny: 98,
    risk_level: "low",
    risk_message: "风险低",
    margin_pct: 25,
    effective_tariff_rate: 0.1,
    feasibility_score: 70,
    financing_ready_score: 80,
    hs_code: "1905",
    hs_description: "面包、糕点、饼干",
    freight_risk: "low",
    conflict_level: "low",
    sentiment_avg_score: 0.2,
    best_landed_cost_usd: 18.5,
    source_quality: "demo",
    hs_verified: false,
    warnings: [],
    ...overrides,
  } as TradeDecision;
}

describe("tradeVerdict 分量计算", () => {
  it("scoreProfit 按 0–35% 线性映射，≥35% 满分", () => {
    expect(scoreProfit(35)).toBe(100);
    expect(scoreProfit(17.5)).toBe(50);
    expect(scoreProfit(0)).toBe(0);
    expect(scoreProfit(-5)).toBe(0);
    expect(scoreProfit(60)).toBe(100);
  });

  it("scoreCash 按天数分档", () => {
    expect(scoreCash(30)).toBe(100);
    expect(scoreCash(45)).toBe(100);
    expect(scoreCash(90)).toBe(75);
    expect(scoreCash(120)).toBe(50);
    expect(scoreCash(200)).toBe(30);
  });

  it("scoreRisk 按等级给基础分并受物流/冲突/低毛利影响", () => {
    expect(scoreRisk(makePayload())).toBe(90);
    expect(scoreRisk(makePayload({ risk_level: "high" }))).toBe(20);
    expect(scoreRisk(makePayload({ risk_level: "high", freight_risk: "high" }))).toBe(10);
    expect(scoreRisk(makePayload({ risk_level: "medium", conflict_level: "medium" }))).toBe(55);
    // 场景毛利跌破 12% 时扣分
    expect(scoreRisk(makePayload(), 8)).toBe(78);
    expect(scoreRisk(makePayload(), 0)).toBe(60);
  });

  it("scoreDemand 优先市场对比行，其次舆情分，最后默认 50", () => {
    expect(scoreDemand(makePayload(), { avg_sales_volume: 80, avg_competition_index: 30 })).toBe(88);
    expect(scoreDemand(makePayload({ sentiment_avg_score: 0.5 }), null)).toBe(75);
    expect(scoreDemand(makePayload({ sentiment_avg_score: Number.NaN }), null)).toBe(50);
  });
});

describe("computeDecisionScore 裁决", () => {
  it("高毛利低风险 → 建议进入", () => {
    const result = computeDecisionScore(makePayload({ margin_pct: 30, risk_level: "low" }));
    expect(result.verdict).toBe("enter");
    expect(result.verdictLabel).toBe("建议进入");
    expect(result.score).toBeGreaterThanOrEqual(74);
  });

  it("低毛利 → 暂缓进入", () => {
    const result = computeDecisionScore(makePayload({ margin_pct: 5, risk_level: "medium" }));
    expect(result.verdict).toBe("hold");
    expect(result.reasons.some((reason) => reason.includes("低于 12% 门槛"))).toBe(true);
  });

  it("高风险等级即使高分也降级为小批试单", () => {
    const result = computeDecisionScore(
      makePayload({ margin_pct: 30, risk_level: "high", freight_risk: "high" }),
    );
    expect(result.score).toBeLessThan(74);
    expect(["trial", "hold"]).toContain(result.verdict);
  });

  it("高分且约束满足 → 建议进入；中分 → 小批试单", () => {
    // 高分：需求/利润/现金全满分，风险 90，可行性 60 融资 60 → 93.3 分
    const high = computeDecisionScore(
      makePayload({
        margin_pct: 35,
        risk_level: "low",
        freight_risk: "low",
        conflict_level: "low",
        feasibility_score: 60,
        financing_ready_score: 60,
      }),
      {
        marketCompareRow: { avg_sales_volume: 80, avg_competition_index: 0 },
        cashDays: 40,
      },
    );
    expect(high.score).toBeGreaterThanOrEqual(74);
    expect(high.verdict).toBe("enter");
    // 中分：毛利 17.5%（利润 50）、需求 70、现金 75、风险 60 → ≈63 分 → 小批试单
    const mid = computeDecisionScore(
      makePayload({
        margin_pct: 17.5,
        risk_level: "medium",
        freight_risk: "low",
        conflict_level: "low",
        sentiment_avg_score: 0.4,
      }),
    );
    expect(mid.score).toBeGreaterThanOrEqual(62);
    expect(mid.score).toBeLessThan(74);
    expect(mid.verdict).toBe("trial");
  });

  it("策略权重影响总分（增长策略需求权重更高）", () => {
    const payload = makePayload({ margin_pct: 20, risk_level: "medium" });
    const growth = computeDecisionScore(payload, {
      strategy: "growth",
      marketCompareRow: { avg_sales_volume: 80, avg_competition_index: 10 },
    });
    const profit = computeDecisionScore(payload, {
      strategy: "profit",
      marketCompareRow: { avg_sales_volume: 10, avg_competition_index: 90 },
    });
    expect(growth.components.demand).toBeGreaterThan(profit.components.demand);
    expect(growth.score).toBeGreaterThan(profit.score);
  });

  it("缺字段回退：需求默认 50、可行性/融资默认 50", () => {
    const result = computeDecisionScore(
      makePayload({
        sentiment_avg_score: undefined,
        feasibility_score: undefined,
        financing_ready_score: undefined,
      }),
    );
    expect(result.components.demand).toBe(50);
    expect(result.components.feasibility).toBe(50);
    expect(result.components.financing).toBe(50);
  });
});

describe("applyTradeAction 一键动作", () => {
  const base = {
    unit_price_usd: 40,
    procurement_cost_cny: 100,
    quantity: 300,
    ad_rate: 0.12,
    return_rate: 0.03,
    inventory_days: 45,
    fx_rate: 7.15,
    landed_cost_usd: 20,
  };

  it("动作清单包含五个预设动作", () => {
    expect(TRADE_ACTIONS.map((action) => action.id)).toEqual([
      "price_up",
      "cost_down",
      "ad_up",
      "air_route",
      "cost_shock",
    ]);
  });

  it("提价 3%", () => {
    const next = applyTradeAction(base, "price_up");
    expect(next.unit_price_usd).toBeCloseTo(41.2, 1);
  });

  it("采购降本 5%", () => {
    const next = applyTradeAction(base, "cost_down");
    expect(next.procurement_cost_cny).toBeCloseTo(95, 0);
  });

  it("广告加码 2 点", () => {
    const next = applyTradeAction(base, "ad_up");
    expect(next.ad_rate).toBeCloseTo(0.14, 2);
  });

  it("切换空运：到岸成本 +15%", () => {
    const next = applyTradeAction(base, "air_route");
    expect(next.landed_cost_usd).toBeCloseTo(23, 0);
  });

  it("成本冲击：采购与到岸成本均 +10%", () => {
    const next = applyTradeAction(base, "cost_shock");
    expect(next.procurement_cost_cny).toBeCloseTo(110, 0);
    expect(next.landed_cost_usd).toBeCloseTo(22, 0);
  });

  it("不动其他输入", () => {
    const next = applyTradeAction(base, "price_up");
    expect(next.quantity).toBe(300);
    expect(next.return_rate).toBe(0.03);
    expect(next.fx_rate).toBe(7.15);
  });
});

describe("buildScenarioVerdict 沙盘测算", () => {
  it("返回场景测算与裁决，且场景利润用于裁决", () => {
    const payload = makePayload({ margin_pct: 25 });
    const { scenario, verdict } = buildScenarioVerdict(payload, {
      unit_price_usd: 40,
      procurement_cost_cny: 100,
      quantity: 300,
      ad_rate: 0.12,
      return_rate: 0.03,
      inventory_days: 45,
      fx_rate: 7.15,
      landed_cost_usd: 20,
    });
    expect(scenario.revenue).toBeGreaterThan(0);
    expect(scenario.net_profit).toBeGreaterThan(0);
    expect(verdict.score).toBeGreaterThan(0);
    expect(verdict.cashDays).toBeGreaterThan(0);
  });

  it("成本冲击后净利润下降", () => {
    const payload = makePayload({ margin_pct: 25 });
    const normal = buildScenarioVerdict(payload, {
      unit_price_usd: 40,
      procurement_cost_cny: 100,
      quantity: 300,
      ad_rate: 0.12,
      return_rate: 0.03,
      inventory_days: 45,
      fx_rate: 7.15,
      landed_cost_usd: 20,
    });
    const shocked = buildScenarioVerdict(
      payload,
      applyTradeAction(
        {
          unit_price_usd: 40,
          procurement_cost_cny: 100,
          quantity: 300,
          ad_rate: 0.12,
          return_rate: 0.03,
          inventory_days: 45,
          fx_rate: 7.15,
          landed_cost_usd: 20,
        },
        "cost_shock",
      ),
    );
    expect(shocked.scenario.net_profit).toBeLessThan(normal.scenario.net_profit);
  });
});

describe("TRADE_PRESETS 方案预设", () => {
  it("包含四套预设且字段完整", () => {
    expect(TRADE_PRESETS).toHaveLength(4);
    for (const preset of TRADE_PRESETS) {
      expect(preset.id).toBeTruthy();
      expect(preset.label).toBeTruthy();
      expect(preset.category).toBeTruthy();
      expect(preset.market).toBeTruthy();
      expect(preset.price).toBeGreaterThan(0);
      expect(preset.cost).toBeGreaterThan(0);
      expect(["balanced", "growth", "profit", "risk"]).toContain(preset.strategy);
    }
  });
});
