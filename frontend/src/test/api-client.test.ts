import { describe, expect, it, vi } from "vitest";
import {
  apiUpload,
  buildGlobePicksFromRows,
  filterRecommendationsOffline,
  fetchGlobeMarketPicks,
  fetchRecommendations,
  fetchResearch,
  fetchJobs,
  postCrawlerSignal,
  saveAiConfig,
} from "@/shared/api/client";

function jsonResponse(payload: unknown) {
  return {
    ok: true,
    status: 200,
    json: async () => payload,
    text: async () => JSON.stringify(payload),
    blob: async () => new Blob([JSON.stringify(payload)]),
  } as Response;
}

function fetchMockCall(index: number): [string, RequestInit] {
  const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
  return fetchMock.mock.calls[index] as unknown as [string, RequestInit];
}

describe("api client", () => {
  it("fetchJobs reads the job registry", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          count: 1,
          items: [{ name: "daily_update", label: "每日数据更新", status: "idle" }],
        }),
      ),
    );
    const data = await fetchJobs();
    expect(data.count).toBe(1);
    expect(data.items[0].name).toBe("daily_update");
    vi.unstubAllGlobals();
  });

  it("saveAiConfig posts the masked payload to backend", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({ configured: true, model: "deepseek-chat" }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await saveAiConfig({ model: "deepseek-chat", timeout: 45 });
    const [url, init] = fetchMock.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toBe("/api/ai/config");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toMatchObject({ timeout: 45 });
    vi.unstubAllGlobals();
  });

  it("apiUpload sends FormData to /api/eda", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({ title: "数据体检", anomalies: [] }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["a,b\n1,2"], "data.csv", { type: "text/csv" });
    const data = await apiUpload<{ title: string; anomalies: unknown[] }>(
      "/api/eda",
      file,
    );
    const [url, init] = fetchMock.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toBe("/api/eda");
    expect(init.body).toBeInstanceOf(FormData);
    expect(data.title).toBe("数据体检");
    vi.unstubAllGlobals();
  });

  it("fetchResearch unwraps the nested research payload", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          research: {
            summary: "完成 4 组联网检索",
            sources: [{ title: "来源一" }],
            provider: "mock",
          },
          keyword: "latiao spicy snack",
        }),
      ),
    );
    const data = await fetchResearch({ keyword: "latiao spicy snack", market: "us" });
    expect(data.summary).toBe("完成 4 组联网检索");
    expect(data.sources).toHaveLength(1);
    expect(data.provider).toBe("mock");
    vi.unstubAllGlobals();
  });

  it("fetchRecommendations builds market-scoped query params", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          count: 2,
          items: [{ category: "cn_latiao", market: "us", six_dimension_score: 80 }],
        }),
      ),
    );
    const data = await fetchRecommendations({ market: "us", top: 8, include_no_go: true });
    const [url] = fetchMockCall(0);
    expect(url).toBe("/api/recommendations?market=us&include_no_go=true&top=8");
    expect(data.count).toBe(2);
    vi.unstubAllGlobals();
  });

  it("fetchRecommendations omits empty params", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ count: 0, items: [] })),
    );
    await fetchRecommendations({});
    const [url] = fetchMockCall(0);
    expect(url).toBe("/api/recommendations");
    vi.unstubAllGlobals();
  });

  it("filterRecommendationsOffline keeps No-Go rows when include_no_go=true", () => {
    const rows = [
      { category: "cn_latiao", market: "us", verdict: "Go", six_dimension_score: 80 },
      { category: "cn_latiao", market: "us", verdict: "No-Go", six_dimension_score: 30 },
      { category: "cn_latiao", market: "vn", verdict: "Conditional", six_dimension_score: 60 },
    ];
    const withNoGo = filterRecommendationsOffline(rows, { include_no_go: true });
    expect(withNoGo).toHaveLength(3);
    const defaultOnly = filterRecommendationsOffline(rows, {});
    expect(defaultOnly).toHaveLength(2);
    expect(defaultOnly.some((r) => r.verdict === "No-Go")).toBe(false);
    // 按六维分降序
    expect(Number(defaultOnly[0].six_dimension_score)).toBeGreaterThan(
      Number(defaultOnly[1].six_dimension_score),
    );
    // 市场过滤
    const usOnly = filterRecommendationsOffline(rows, { market: "us" });
    expect(usOnly).toHaveLength(1);
  });

  it("fetchGlobeMarketPicks groups market-scoped top picks", async () => {
    const marketIds = ["us", "eu", "sea"];
    const fetchMock = vi.fn(async (url: string) =>
      jsonResponse({
        count: 4,
        items: ["cn_latiao", "cn_longjing", "cn_frozen_dumplings", "cn_beef_jerky"].map((category, index) => ({
          category,
          category_name: category === "cn_latiao" ? "辣条" : category,
          market: url.includes("market=us")
            ? "us"
            : url.includes("market=eu")
              ? "eu"
              : "sea",
          six_dimension_score: 82 - index,
          verdict: "Go",
          forecast_growth: 12.5 - index,
        })),
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const data = await fetchGlobeMarketPicks(marketIds);
    const urls = fetchMock.mock.calls.map((call) => String(call[0]));

    expect(urls).toHaveLength(3);
    expect(urls).toContain("/api/recommendations?market=us&top=4");
    expect(urls).toContain("/api/recommendations?market=eu&top=4");
    expect(urls).toContain("/api/recommendations?market=sea&top=4");
    expect(data.us).toHaveLength(4);
    expect(data.us[0]).toMatchObject({
      category: "cn_latiao",
      category_name: "辣条",
      market: "us",
      six_dimension_score: 82,
      verdict: "Go",
      forecast_growth: 12.5,
    });
    vi.unstubAllGlobals();
  });

  it("buildGlobePicksFromRows keeps Go/Conditional and sorts top 4 per market", () => {
    const rows = [
      {
        category: "cn_longjing",
        market: "us",
        verdict: "No-Go",
        six_dimension_score: 90,
        forecast_growth: 5,
      },
      {
        category: "cn_frozen_dumplings",
        market: "us",
        verdict: "Go",
        six_dimension_score: 91,
        forecast_growth: 18,
      },
      {
        category: "cn_changsha_mifen",
        market: "us",
        verdict: "Go",
        six_dimension_score: 88,
        forecast_growth: 12,
      },
      {
        category: "cn_latiao",
        market: "us",
        category_name: "辣条",
        verdict: "Conditional",
        six_dimension_score: 80,
        forecast_growth: 9,
      },
      {
        category: "cn_laoganma",
        market: "us",
        verdict: "Go",
        six_dimension_score: 75,
        forecast_growth: 7,
      },
      {
        category: "intl_firm_tofu",
        market: "us",
        verdict: "Go",
        six_dimension_score: 70,
        forecast_growth: 4,
      },
    ];

    const data = buildGlobePicksFromRows(["us", "vn"], rows);

    expect(data.us).toHaveLength(4);
    expect(data.us.map((pick) => pick.category)).toEqual([
      "cn_frozen_dumplings",
      "cn_changsha_mifen",
      "cn_latiao",
      "cn_laoganma",
    ]);
    expect(data.us[0]).toMatchObject({
      category: "cn_frozen_dumplings",
      six_dimension_score: 91,
      verdict: "Go",
    });
    expect(data.us[2].category_name).toBe("辣条");
    expect(data.vn).toEqual([]);
  });

  it("fetchGlobeMarketPicks backfills markets with fewer than 4 recommendable rows", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      if (url.includes("include_no_go=true")) {
        return jsonResponse({
          count: 3,
          items: [
            {
              category: "cn_longjing",
              category_name: "西湖龙井",
              market: "us",
              six_dimension_score: 74,
              verdict: "No-Go",
              forecast_growth: 6,
            },
            {
              category: "cn_mooncake",
              category_name: "广式月饼",
              market: "us",
              six_dimension_score: 73,
              verdict: "No-Go",
              forecast_growth: 5,
            },
            {
              category: "cn_frozen_dumplings",
              category_name: "速冻水饺",
              market: "us",
              six_dimension_score: 72,
              verdict: "No-Go",
              forecast_growth: 4,
            },
          ],
        });
      }
      return jsonResponse({
        count: 1,
        items: [
          {
            category: "cn_latiao",
            category_name: "辣条",
            market: "us",
            six_dimension_score: 80,
            verdict: "Conditional",
            forecast_growth: 10,
          },
        ],
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const data = await fetchGlobeMarketPicks(["us"]);
    const urls = fetchMock.mock.calls.map((call) => String(call[0]));

    expect(data.us).toHaveLength(4);
    expect(data.us[0]).toMatchObject({
      category: "cn_latiao",
      verdict: "Conditional",
      six_dimension_score: 80,
    });
    expect(data.us.slice(1).map((pick) => pick.verdict)).toEqual([
      "No-Go",
      "No-Go",
      "No-Go",
    ]);
    expect(urls).toContain("/api/recommendations?market=us&top=4");
    expect(urls).toContain(
      "/api/recommendations?market=us&include_no_go=true&top=4",
    );
    vi.unstubAllGlobals();
  });

  it("buildGlobePicksFromRows fills markets that only have No-Go rows", () => {
    const rows = [
      {
        category: "cn_beef_jerky",
        market: "us",
        verdict: "No-Go",
        six_dimension_score: 90,
        forecast_growth: 12,
      },
      {
        category: "cn_latiao",
        market: "us",
        verdict: "No-Go",
        six_dimension_score: 80,
        forecast_growth: 9,
      },
      {
        category: "cn_longjing",
        market: "us",
        verdict: "No-Go",
        six_dimension_score: 70,
        forecast_growth: 6,
      },
      {
        category: "cn_frozen_dumplings",
        market: "us",
        verdict: "No-Go",
        six_dimension_score: 60,
        forecast_growth: 4,
      },
      {
        category: "cn_mooncake",
        market: "us",
        verdict: "No-Go",
        six_dimension_score: 50,
        forecast_growth: 2,
      },
    ];

    const data = buildGlobePicksFromRows(["us"], rows);

    expect(data.us).toHaveLength(4);
    expect(data.us.map((pick) => pick.category)).toEqual([
      "cn_beef_jerky",
      "cn_latiao",
      "cn_longjing",
      "cn_frozen_dumplings",
    ]);
    expect(data.us.every((pick) => pick.verdict === "No-Go")).toBe(true);
  });

  it("postCrawlerSignal wraps a live signal into combos", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({
          keyword: "latiao spicy snack",
          market: "us",
          category: "cn_latiao",
          fallback_used: true,
          source_count: 3,
        }),
      ),
    );
    const data = await postCrawlerSignal({ keyword: "latiao spicy snack" });
    expect(data.count).toBe(1);
    expect(data.combos).toHaveLength(1);
    expect(data.status).toBe("fallback");
    vi.unstubAllGlobals();
  });
});
