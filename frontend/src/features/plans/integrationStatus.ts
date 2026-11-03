export type StatusTone = "green" | "amber" | "red" | "cyan" | "neutral";

const READY_WORDS = new Set([
  "ready",
  "ok",
  "enabled",
  "true",
  "online",
  "connected",
  "done",
  "success",
]);
const WARN_WORDS = new Set([
  "fallback",
  "mock",
  "partial",
  "warning",
  "warn",
]);
const ERROR_WORDS = new Set([
  "error",
  "fail",
  "failed",
  "unavailable",
  "missing",
  "offline",
]);

function asString(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value).trim().toLowerCase();
}

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

export function sourceTone(input: {
  status?: unknown;
  fallbackUsed?: unknown;
  provider?: unknown;
  errorCount?: unknown;
}): StatusTone {
  const status = asString(input.status);
  const provider = asString(input.provider);
  const errorCount = asNumber(input.errorCount) ?? 0;

  if (ERROR_WORDS.has(status) || (status === "" && errorCount > 0)) {
    return "red";
  }
  if (
    WARN_WORDS.has(status) ||
    input.fallbackUsed === true ||
    provider === "mock"
  ) {
    return "amber";
  }
  if (READY_WORDS.has(status) || provider !== "") {
    return "green";
  }
  return "neutral";
}

export function sourceStatusLabel(input: {
  status?: unknown;
  fallbackUsed?: unknown;
  provider?: unknown;
  errorCount?: unknown;
}): string {
  const tone = sourceTone(input);
  if (tone === "red") return "异常";
  if (tone === "amber") return "回退";
  if (tone === "green") return "就绪";
  return "未知";
}

export function jobTone(status: unknown): StatusTone {
  const value = asString(status);
  if (value === "running") return "cyan";
  if (["done", "ok", "success", "ready"].includes(value)) return "green";
  if (["error", "failed", "cancelled"].includes(value)) return "red";
  return "neutral";
}

export function jobLabel(status: unknown): string {
  const value = asString(status);
  const labels: Record<string, string> = {
    running: "运行中",
    done: "完成",
    ok: "完成",
    success: "完成",
    ready: "就绪",
    error: "错误",
    failed: "错误",
    cancelled: "已取消",
    idle: "空闲",
  };
  return labels[value] ?? (value || "--");
}

export function providerLabel(provider: unknown): string {
  const value = asString(provider);
  const labels: Record<string, string> = {
    pytrends: "Google Trends",
    comtrade: "UN Comtrade",
    ots: "Open Trade Statistics",
    duckduckgo_html: "DuckDuckGo",
    wikimedia_search: "Wikimedia",
    mock: "模拟",
    "1688_cli": "1688 CLI",
    amazon_github: "Amazon 样例",
    ebay_github: "eBay 样例",
    github: "GitHub 公开数据",
    open_food_facts: "Open Food Facts",
  };
  return labels[value] ?? (value || "--");
}

export function coverageLabel(coverage: unknown): string {
  const numeric = asNumber(coverage);
  if (numeric !== null) return `${numeric} 条`;
  if (!coverage || typeof coverage !== "object") return "--";

  const record = coverage as Record<string, unknown>;
  const requested = asNumber(record.requested);
  const real = asNumber(record.real);
  const mock = asNumber(record.mock);
  const parts: string[] = [];
  if (real !== null) parts.push(`真实 ${real}`);
  if (mock !== null) parts.push(`模拟 ${mock}`);
  if (requested !== null) parts.push(`共 ${requested}`);
  return parts.length ? parts.join(" / ") : "--";
}

export function fallbackLabel(fallbackUsed: unknown): string {
  if (fallbackUsed === true) return "含回退";
  if (fallbackUsed === false) return "真实";
  return "--";
}
