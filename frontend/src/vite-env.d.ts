/// <reference types="vite/client" />

import type { DashboardData } from "@/shared/api/types";

declare global {
  interface Window {
    __TRADE_INTEL_OFFLINE__?: DashboardData;
    __TRADE_INTEL_OFFLINE_GZIP__?: string;
  }
}

declare module "*.png?inline" {
  const src: string;
  export default src;
}

declare module "*.jpg?inline" {
  const src: string;
  export default src;
}

interface ImportMetaEnv {
  /** 前端请求后端 API 的完整 URL；留空 = 同源（生产 /app 部署） */
  readonly VITE_API_BASE?: string;
  /** pnpm dev 时 /api 与 /output 的代理目标，默认 http://127.0.0.1:8000 */
  readonly VITE_PROXY_TARGET?: string;
  readonly VITE_OFFLINE?: string;
}
