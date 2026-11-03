import type { DashboardData } from "./types";

export const IS_OFFLINE = import.meta.env.VITE_OFFLINE === "1";

export function getOfflineData(): DashboardData | null {
  if (!IS_OFFLINE) {
    return null;
  }
  return window.__TRADE_INTEL_OFFLINE__ ?? null;
}

export async function initOfflineData(): Promise<void> {
  if (!IS_OFFLINE || window.__TRADE_INTEL_OFFLINE__) {
    return;
  }
  const encoded = window.__TRADE_INTEL_OFFLINE_GZIP__;
  if (!encoded) {
    return;
  }
  const binary = atob(encoded);
  const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
  const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
  const text = await new Response(stream).text();
  window.__TRADE_INTEL_OFFLINE__ = JSON.parse(text) as DashboardData;
}
