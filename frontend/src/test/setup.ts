import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

if (!window.matchMedia) {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }),
  });
}

// 静默 jsdom 未实现的 canvas/scrollTo 告警（S2：Three.js/GSAP 组件在测试环境触发）
HTMLCanvasElement.prototype.getContext = vi.fn(() => null) as never;
window.scrollTo = vi.fn() as never;
window.scrollBy = vi.fn() as never;
