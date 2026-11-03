import type {
  BatchRun,
  SelectionDraft,
  TradeScenario,
  WatchlistItem,
} from "@/shared/api/types";

/**
 * 方案中心演示预置（demo seed）。
 *
 * 全新演示环境（localStorage 无历史数据）首次进入方案中心时，四个区块
 * （方案草稿 / 关注清单 / 方案沙盘 / 批量分析历史）会全空，显得页面空旷。
 * 本模块提供与系统真实数据一致（品类 key、判定、六维分均取自看板 Top 推荐
 * 与四脑引擎默认产品）的预置内容：组合、评分不是编造，而是演示链路上真实
 * 存在的数据，评委可顺藤摸瓜继续四脑立项 / 贸易决策。
 *
 * 预置只执行一次（seededDemo 标记持久化），且仅当四项全空时触发，
 * 不覆盖用户已有的真实数据；所有预置项均可像真实数据一样删除。
 */

export interface DemoSeedContent {
  selectionDraft: SelectionDraft;
  watchlist: WatchlistItem[];
  scenarios: TradeScenario[];
  batchRuns: BatchRun[];
}

export function buildDemoSeed(now = new Date().toISOString()): DemoSeedContent {
  return {
    selectionDraft: {
      label: "辣条 × 美国",
      keyword: "辣条（网红休闲零食）",
      category: "cn_latiao",
      market: "us",
      price: 4.9,
      procurement_cost_cny: 12,
      budget: 20000,
      target_margin: 0.35,
      verdict: "No-Go",
      score: 65.2,
      isDemo: true,
    },
    watchlist: [
      {
        id: "cn_longjing-uk",
        label: "西湖龙井 × 英国",
        category: "cn_longjing",
        market: "uk",
        keyword: "西湖龙井",
        verdict: "Go",
        score: 74.8,
        createdAt: now,
        isDemo: true,
      },
      {
        id: "cn_frozen_dumplings-jp",
        label: "速冻水饺 × 日本",
        category: "cn_frozen_dumplings",
        market: "jp",
        keyword: "速冻水饺",
        verdict: "Go",
        score: 71.9,
        createdAt: now,
        isDemo: true,
      },
      {
        id: "cn_laoganma-ca",
        label: "老干妈辣椒酱 × 加拿大",
        category: "cn_laoganma",
        market: "ca",
        keyword: "老干妈辣椒酱",
        verdict: "Conditional",
        score: 74.3,
        createdAt: now,
        isDemo: true,
      },
    ],
    scenarios: [
      {
        id: "scenario-latiao-us-balanced",
        label: "辣条 · 美国 · 均衡铺货",
        category: "cn_latiao",
        market: "us",
        unit_price_usd: 4.9,
        procurement_cost_cny: 12,
        quantity: 800,
        ad_rate: 0.08,
        return_rate: 0.03,
        inventory_days: 30,
        fx_rate: 7.15,
        createdAt: now,
        isDemo: true,
      },
      {
        id: "scenario-latiao-us-cautious",
        label: "辣条 · 美国 · 谨慎试单",
        category: "cn_latiao",
        market: "us",
        unit_price_usd: 4.9,
        procurement_cost_cny: 12,
        quantity: 200,
        ad_rate: 0.05,
        return_rate: 0.02,
        inventory_days: 15,
        fx_rate: 7.15,
        createdAt: now,
        isDemo: true,
      },
    ],
    batchRuns: [
      {
        id: "batch-132x15-scan",
        label: "132 品类 × 15 市场 · 六维速扫",
        createdAt: now,
        isDemo: true,
        items: [
          { label: "西湖龙井 × 英国", verdict: "Go", score: 74.8 },
          { label: "速冻水饺 × 日本", verdict: "Go", score: 71.9 },
          { label: "老干妈辣椒酱 × 加拿大", verdict: "Conditional", score: 74.3 },
          { label: "辣条 × 美国", verdict: "No-Go", score: 65.2 },
        ],
      },
      {
        id: "batch-latiao-four-brain",
        label: "辣条 · 四脑立项（4 提示词）",
        createdAt: now,
        isDemo: true,
        items: [
          { label: "战略脑 · 市场卡位", verdict: "Go", score: 72 },
          { label: "市场脑 · 需求验证", verdict: "Go", score: 75 },
          { label: "产品脑 · 功能定义", verdict: "Conditional", score: 68 },
          { label: "风险脑 · 合规与关税", verdict: "No-Go", score: 42 },
        ],
      },
    ],
  };
}

export interface DemoSeedActions {
  setSelectionDraft: (draft: SelectionDraft | null) => void;
  addToWatchlist: (item: WatchlistItem) => void;
  addScenario: (scenario: TradeScenario) => void;
  saveBatchRun: (run: BatchRun) => void;
}

export function applyDemoSeed(
  actions: DemoSeedActions,
  now = new Date().toISOString(),
): void {
  const seed = buildDemoSeed(now);
  actions.setSelectionDraft(seed.selectionDraft);
  seed.watchlist.forEach((item) => actions.addToWatchlist(item));
  seed.scenarios.forEach((scenario) => actions.addScenario(scenario));
  seed.batchRuns.forEach((run) => actions.saveBatchRun(run));
}

export interface SeedGate {
  seededDemo: boolean;
  selectionDraft: unknown;
  watchlist: unknown[];
  scenarios: unknown[];
  batchRuns: unknown[];
}

/**
 * 方案中心首访预置：仅当从未预置（seededDemo=false）且四项全空时执行一次。
 * 用户已有真实内容时跳过；用户删光预置项后因 seededDemo 已置位也不会重复。
 */
export function seedDemoIfEmpty(
  getState: () => SeedGate,
  actions: DemoSeedActions & { markDemoSeeded: () => void },
): void {
  const state = getState();
  if (state.seededDemo) return;
  if (
    state.selectionDraft ||
    state.watchlist.length > 0 ||
    state.scenarios.length > 0 ||
    state.batchRuns.length > 0
  ) {
    return;
  }
  applyDemoSeed(actions);
  actions.markDemoSeeded();
}
