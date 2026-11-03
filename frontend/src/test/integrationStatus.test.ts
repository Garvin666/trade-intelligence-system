import { describe, expect, it } from "vitest";
import {
  coverageLabel,
  fallbackLabel,
  jobLabel,
  jobTone,
  providerLabel,
  sourceStatusLabel,
  sourceTone,
} from "@/features/plans/integrationStatus";

describe("integrationStatus 状态归一化", () => {
  it("sourceTone 按就绪/回退/异常/未知映射", () => {
    expect(sourceTone({ status: "ready", fallbackUsed: false, provider: "comtrade" })).toBe(
      "green",
    );
    expect(sourceTone({ status: "ready", fallbackUsed: true, provider: "pytrends" })).toBe(
      "amber",
    );
    expect(sourceTone({ status: "fallback", provider: "duckduckgo_html" })).toBe("amber");
    expect(sourceTone({ provider: "mock" })).toBe("amber");
    expect(sourceTone({ status: "error", provider: "1688_cli" })).toBe("red");
    expect(sourceTone({ provider: "wikimedia_search" })).toBe("green");
    expect(sourceTone({})).toBe("neutral");
  });

  it("sourceStatusLabel 输出中文状态", () => {
    expect(sourceStatusLabel({ status: "ready", fallbackUsed: false })).toBe("就绪");
    expect(sourceStatusLabel({ status: "ready", fallbackUsed: true })).toBe("回退");
    expect(sourceStatusLabel({ provider: "mock" })).toBe("回退");
    expect(sourceStatusLabel({ status: "error" })).toBe("异常");
    expect(sourceStatusLabel({})).toBe("未知");
  });

  it("jobTone 与 jobLabel 覆盖任务状态", () => {
    expect(jobTone("running")).toBe("cyan");
    expect(jobTone("done")).toBe("green");
    expect(jobTone("error")).toBe("red");
    expect(jobTone("idle")).toBe("neutral");
    expect(jobLabel("running")).toBe("运行中");
    expect(jobLabel("done")).toBe("完成");
    expect(jobLabel("error")).toBe("错误");
    expect(jobLabel("idle")).toBe("空闲");
    expect(jobLabel(undefined)).toBe("--");
  });

  it("providerLabel 使用可读名称并保留未知值", () => {
    expect(providerLabel("pytrends")).toBe("Google Trends");
    expect(providerLabel("1688_cli")).toBe("1688 CLI");
    expect(providerLabel("custom_provider")).toBe("custom_provider");
    expect(providerLabel(undefined)).toBe("--");
  });

  it("coverageLabel 处理数字与覆盖对象", () => {
    expect(coverageLabel(990)).toBe("990 条");
    expect(coverageLabel({ requested: 66, real: 10, mock: 56 })).toBe(
      "真实 10 / 模拟 56 / 共 66",
    );
    expect(coverageLabel({ real: 13, mock: 2 })).toBe("真实 13 / 模拟 2");
    expect(coverageLabel(null)).toBe("--");
  });

  it("fallbackLabel 区分真实与回退", () => {
    expect(fallbackLabel(true)).toBe("含回退");
    expect(fallbackLabel(false)).toBe("真实");
    expect(fallbackLabel(undefined)).toBe("--");
  });
});
