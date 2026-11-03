export interface TradeScenarioInput {
  category: string;
  market: string;
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

export interface TradeScenarioResult {
  revenue: number;
  landed_cost_usd: number;
  platform_fee: number;
  ad_cost: number;
  return_cost: number;
  net_profit: number;
  margin_pct: number;
  contribution: number;
  break_even_units: number;
  cash_days: number;
}

export function calculateTradeScenario(
  input: TradeScenarioInput,
): TradeScenarioResult {
  const fx = input.fx_rate > 0 ? input.fx_rate : 7.15;
  const commissionRate = input.platform_commission_rate ?? 0.15;
  const landedCostUsd =
    input.landed_cost_usd ?? input.procurement_cost_cny / fx + 2.5;
  const revenue = input.unit_price_usd * input.quantity;
  const landedTotal = landedCostUsd * input.quantity;
  const platformFee = revenue * commissionRate;
  const adCost = revenue * input.ad_rate;
  const returnCost = revenue * input.return_rate;
  const netProfit = revenue - landedTotal - platformFee - adCost - returnCost;
  const contribution =
    input.unit_price_usd -
    landedCostUsd -
    input.unit_price_usd * commissionRate -
    input.unit_price_usd * input.ad_rate -
    input.unit_price_usd * input.return_rate;
  return {
    revenue: round(revenue),
    landed_cost_usd: round(landedCostUsd),
    platform_fee: round(platformFee),
    ad_cost: round(adCost),
    return_cost: round(returnCost),
    net_profit: round(netProfit),
    margin_pct: round(revenue > 0 ? (netProfit / revenue) * 100 : 0),
    contribution: round(contribution),
    break_even_units:
      contribution > 0 ? Math.ceil(input.quantity / Math.max(contribution, 1e-6)) : Number.POSITIVE_INFINITY,
    cash_days: input.inventory_days + (input.payment_days ?? 30),
  };
}

function round(value: number): number {
  return Math.round(value * 100) / 100;
}
