import {
  Activity,
  BadgeCheck,
  Banknote,
  Bot,
  BrainCircuit,
  Calculator,
  CircleDollarSign,
  ClipboardCheck,
  Cpu,
  Compass,
  Database,
  FileSearch,
  FileText,
  Gavel,
  Package,
  Radio,
  ShieldAlert,
  ShieldCheck,
  Ship,
  Sparkles,
  Star,
  Target,
  TrendingUp,
  Wallet,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { Fragment, useEffect, useRef } from "react";
import { cn } from "@/shared/lib/utils";
import { LogoMark } from "@/shared/brand/LogoMark";

/**
 * Page3DScene 的 CSS 3D 降级场景（无 WebGL / 懒加载期 / 降级路径）。
 *
 * 相比纯静态面板，此版本用 CSS 3D（perspective + translateZ 深度层）与
 * JS 驱动的 rAF 动效营造"3D 立体 + 持续动效 + 强交互"：
 *  - 深度层次：品牌区 / 节点链 / 统计卡分布在 Z 轴不同深度，整体舞台随
 *    光标视差倾斜、自动缓慢摆动；
 *  - 动效（rAF 驱动，不受全局 prefers-reduced-motion CSS 规则限制，
 *    用户显式要求动效）：节点上下悬浮（相位错开）、连接光点呼吸、自转摆动；
 *  - 强交互：按住拖拽旋转舞台（松手惯性缓回）、节点悬停弹出（translateZ
 *    前移 + 放大 + 光晕 + 子指标显现）、光标视差跟随。
 * 动效全部经 ref 直写 DOM transform，不触发 React 重渲染。
 */

export type SceneVariant = "default" | "dashboard" | "workbench" | "trade" | "agent";

interface SceneStep {
  label: string;
  icon: LucideIcon;
  detail?: string;
}

interface SceneVariantConfig {
  brand: { title: string; subtitle: string };
  steps: SceneStep[];
  /** 移动端精简链路的三个节点名 */
  compactSteps: string[];
  stats: Array<{ label: string; value: string }>;
}

const DEFAULT_CONFIG: SceneVariantConfig = {
  brand: {
    title: "远帆航线终端",
    subtitle: "132 品类 × 15 市场 · 1980 组合 · 官方源优先",
  },
  steps: [
    { label: "港口", icon: Database, detail: "1980 组合" },
    { label: "清关", icon: Sparkles, detail: "证据闸" },
    { label: "装船", icon: Cpu, detail: "三模型" },
    { label: "航线", icon: TrendingUp, detail: "90 天" },
    { label: "靠港", icon: Star, detail: "Top 20" },
    { label: "决策", icon: Ship, detail: "Go/No-Go" },
  ],
  compactSteps: ["港口", "航线", "决策"],
  stats: [
    { label: "覆盖品类", value: "132" },
    { label: "目标市场", value: "15" },
    { label: "政策事件", value: "21" },
    { label: "预测基线", value: "3" },
  ],
};

const DASHBOARD_CONFIG: SceneVariantConfig = {
  brand: {
    title: "选品看板",
    subtitle: "132 品类 × 15 市场 · 六维评分 · Go/No-Go 判定",
  },
  steps: [
    { label: "需求", icon: Activity, detail: "销量指数" },
    { label: "趋势", icon: TrendingUp, detail: "搜索热度" },
    { label: "竞争", icon: Target, detail: "竞争度" },
    { label: "利润", icon: Wallet, detail: "利润空间" },
    { label: "合规", icon: ShieldCheck, detail: "合规风险" },
    { label: "证据", icon: BadgeCheck, detail: "证据闸" },
  ],
  compactSteps: ["选品", "预测", "判定"],
  stats: [
    { label: "覆盖品类", value: "132" },
    { label: "目标市场", value: "15" },
    { label: "推荐组合", value: "1980" },
    { label: "预测基线", value: "3" },
  ],
};

const WORKBENCH_CONFIG: SceneVariantConfig = {
  brand: {
    title: "四脑工作台",
    subtitle: "多提示词输入 · 四脑并行分析 · 综合报告",
  },
  steps: [
    { label: "输入", icon: FileText, detail: "多提示词" },
    { label: "战略脑", icon: BrainCircuit, detail: "市场卡位" },
    { label: "市场脑", icon: Compass, detail: "需求验证" },
    { label: "产品脑", icon: Package, detail: "功能定义" },
    { label: "风险脑", icon: ShieldAlert, detail: "合规关税" },
    { label: "综合", icon: Sparkles, detail: "立项建议" },
  ],
  compactSteps: ["输入", "四脑", "综合"],
  stats: [
    { label: "并行脑", value: "4" },
    { label: "覆盖品类", value: "132" },
    { label: "目标市场", value: "15" },
    { label: "证据闸", value: "开" },
  ],
};

const TRADE_CONFIG: SceneVariantConfig = {
  brand: {
    title: "贸易决策",
    subtitle: "HS Code 速查 · 卖前体检 · 供应商与客户尽调",
  },
  steps: [
    { label: "HS Code", icon: FileSearch, detail: "六位速查" },
    { label: "关税成本", icon: CircleDollarSign, detail: "到岸测算" },
    { label: "利润测算", icon: Calculator, detail: "敏感性" },
    { label: "卖前体检", icon: ClipboardCheck, detail: "逐项勾选" },
    { label: "融资尽调", icon: Banknote, detail: "融资档位" },
    { label: "裁决", icon: Gavel, detail: "Go/No-Go" },
  ],
  compactSteps: ["成本", "体检", "裁决"],
  stats: [
    { label: "政策事件", value: "21" },
    { label: "汇率基准", value: "7.15" },
    { label: "目标市场", value: "15" },
    { label: "覆盖品类", value: "132" },
  ],
};

const AGENT_CONFIG: SceneVariantConfig = {
  brand: {
    title: "小助手",
    subtitle: "自然语言指令 · 分步执行 · 写操作先确认",
  },
  steps: [
    { label: "意图", icon: Bot, detail: "自然语言" },
    { label: "工具", icon: Wrench, detail: "读即执行" },
    { label: "确认", icon: ShieldCheck, detail: "写先确认" },
    { label: "执行", icon: Cpu, detail: "SSE 分步" },
    { label: "来源", icon: Radio, detail: "证据闸" },
    { label: "完成", icon: BadgeCheck, detail: "会话恢复" },
  ],
  compactSteps: ["指令", "工具", "确认"],
  stats: [
    { label: "读操作", value: "即执行" },
    { label: "写操作", value: "需确认" },
    { label: "会话", value: "可恢复" },
    { label: "确认闸", value: "开" },
  ],
};

const VARIANTS: Record<SceneVariant, SceneVariantConfig> = {
  default: DEFAULT_CONFIG,
  dashboard: DASHBOARD_CONFIG,
  workbench: WORKBENCH_CONFIG,
  trade: TRADE_CONFIG,
  agent: AGENT_CONFIG,
};

export function Page3DSceneStatic({
  height = 132,
  className,
  variant = "default",
}: {
  height?: number;
  className?: string;
  variant?: SceneVariant;
}) {
  const config = VARIANTS[variant] ?? DEFAULT_CONFIG;
  const lastIndex = config.steps.length - 1;

  const stageRef = useRef<HTMLDivElement>(null);
  const nodeRefs = useRef<Array<HTMLDivElement | null>>([]);
  const statRefs = useRef<Array<HTMLDivElement | null>>([]);
  const linkDotRefs = useRef<Array<HTMLSpanElement | null>>([]);
  const pulseRef = useRef<HTMLSpanElement>(null);
  const glowRef = useRef<HTMLDivElement>(null);

  // 3D 舞台：纯自动动效（节点悬浮 + 数据光流 + 末端脉冲 + 光晕呼吸），无交互
  // （rAF 直写 transform，不触发 React 重渲染）
  useEffect(() => {
    const stage = stageRef.current;
    if (!stage || typeof window === "undefined") return;
    if (typeof window.requestAnimationFrame !== "function") return;

    let raf = 0;
    let running = true;

    const tick = (time: number) => {
      if (!running) return;
      const t = time * 0.001;

      // 节点悬浮（相位错开，深度弧面固定）
      nodeRefs.current.forEach((node, index) => {
        if (!node) return;
        const float = Math.sin(t * 1.4 + index * 0.85) * 4;
        node.style.transform = `translateY(${float.toFixed(1)}px) translateZ(${16 + index * 8}px)`;
      });
      // 统计卡轻微浮动
      statRefs.current.forEach((stat, index) => {
        if (!stat) return;
        const float = Math.sin(t * 1.1 + index * 1.2) * 3;
        stat.style.transform = `translateY(${float.toFixed(1)}px) translateZ(52px)`;
      });
      // 数据光流：光点沿连接线循环流动（相位错开）
      linkDotRefs.current.forEach((dot, index) => {
        if (!dot) return;
        const progress = (t * 0.32 + index * 0.5) % 1;
        dot.style.left = `${(progress * 100).toFixed(1)}%`;
        dot.style.opacity = String(Math.sin(progress * Math.PI) * 0.9);
      });
      // 末端脉冲：决策节点扩散圆环
      if (pulseRef.current) {
        const p = (t % 2.6) / 2.6;
        pulseRef.current.style.transform = `scale(${(1 + p * 0.75).toFixed(3)})`;
        pulseRef.current.style.opacity = String((1 - p) * 0.55);
      }
      // 光晕呼吸
      if (glowRef.current) {
        glowRef.current.style.opacity = String((0.9 + Math.sin(t * 0.5) * 0.12).toFixed(3));
      }
      raf = window.requestAnimationFrame(tick);
    };
    raf = window.requestAnimationFrame(tick);

    return () => {
      running = false;
      window.cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div
      data-page-3d-static
      data-variant={variant}
      className={cn(
        "relative overflow-hidden rounded-xl border border-white/10 bg-raised/85",
        className,
      )}
      style={{ height, perspective: "900px" }}
    >
      {/* 背景质感：双色光晕（呼吸）+ 点阵网格 + 顶部高光 */}
      <div
        ref={glowRef}
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_72%_18%,rgba(34,211,238,.08),transparent_52%),radial-gradient(circle_at_18%_85%,rgba(245,158,11,.04),transparent_48%)]"
      />
      <div
        className="pointer-events-none absolute inset-0 opacity-40"
        style={{
          backgroundImage:
            "radial-gradient(rgba(148,163,184,.16) 1px, transparent 1px)",
          backgroundSize: "22px 22px",
        }}
      />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/20 to-transparent" />
      <div className="pointer-events-none absolute inset-x-10 bottom-0 h-px bg-gradient-to-r from-transparent via-slate-500/20 to-transparent" />

      {/* 3D 舞台（深度层，纯自动动效） */}
      <div
        ref={stageRef}
        className="relative h-full"
        style={{ transformStyle: "preserve-3d" }}
        aria-hidden="true"
      >
        {/* 左：品牌状态区（深度层 1） */}
        <div
          className="absolute left-4 top-1/2 flex -translate-y-1/2 items-center gap-3 sm:left-6"
          style={{ transformStyle: "preserve-3d" }}
        >
          <div
            className="relative flex h-10 w-10 items-center justify-center rounded-xl border border-accent/25 bg-accent/10 shadow-[0_0_18px_rgba(34,211,238,.18)]"
            style={{ transform: "translateZ(40px)" }}
          >
            <LogoMark size={24} />
            <span className="absolute -right-0.5 -top-0.5 h-2 w-2 animate-pulse rounded-full bg-emerald-400 ring-2 ring-base" />
          </div>
          <div
            className="min-w-0"
            style={{ transform: "translateZ(30px)" }}
          >
            <p className="truncate text-xs font-bold tracking-wide text-white">
              {config.brand.title}
            </p>
            <p className="mt-0.5 hidden truncate text-[11px] text-slate-500 sm:block">
              {config.brand.subtitle}
            </p>
          </div>
        </div>

        {/* 中：流程节点链（深度层 2，节点逐级前移形成弧面；md 以下精简） */}
        <div className="absolute inset-0 hidden items-center justify-center md:flex">
          {config.steps.map((step, index) => {
            const Icon = step.icon;
            const last = index === lastIndex;
            return (
              <Fragment key={step.label}>
                {index > 0 && (
                  <div className="relative mx-1.5 h-px w-6 sm:w-10">
                    <span className="absolute inset-0 bg-gradient-to-r from-accent/30 to-slate-600/30" />
                    {/* 数据光流光点（JS 驱动沿连接线流动） */}
                    <span
                      ref={(dot) => {
                        linkDotRefs.current[index - 1] = dot;
                      }}
                      className="absolute left-0 top-1/2 h-1.5 w-1.5 -translate-y-1/2 rounded-full bg-cyan-200 shadow-[0_0_8px_rgba(34,211,238,.9)]"
                      style={{ willChange: "left, opacity" }}
                    />
                  </div>
                )}
                <div
                  ref={(node) => {
                    nodeRefs.current[index] = node;
                  }}
                  className="flex flex-col items-center gap-1 rounded-xl px-1.5 py-1"
                  style={{
                    transformStyle: "preserve-3d",
                    willChange: "transform",
                  }}
                >
                  <span
                    className={cn(
                      "flex h-8 w-8 items-center justify-center rounded-full border",
                      last
                        ? "border-amber-300/40 bg-amber-300/10 shadow-[0_0_14px_rgba(245,158,11,.25)]"
                        : "border-accent/25 bg-cyan-300/5",
                    )}
                  >
                    {last && (
                      <span
                        ref={pulseRef}
                        className="pointer-events-none absolute inset-0 rounded-full border border-amber-300/70"
                        style={{ willChange: "transform, opacity" }}
                      />
                    )}
                    <Icon
                      className={cn(
                        "h-3.5 w-3.5",
                        last ? "text-amber-200" : "text-accent",
                      )}
                    />
                  </span>
                  <span
                    className={cn(
                      "text-[11px] font-semibold",
                      last ? "text-amber-200" : "text-slate-300",
                    )}
                  >
                    {step.label}
                  </span>
                  <span
                    className={cn(
                      "text-[11px] leading-none opacity-0 transition-opacity duration-200 xl:opacity-100",
                    )}
                    style={{ color: "#475569" }}
                  >
                    {step.detail}
                  </span>
                </div>
              </Fragment>
            );
          })}
        </div>

        {/* 移动端精简链路 */}
        <div className="absolute inset-0 flex items-center justify-center gap-2 md:hidden">
          {config.compactSteps.map((label, index) => {
            const last = index === config.compactSteps.length - 1;
            return (
              <Fragment key={label}>
                {index > 0 && (
                  <span className="h-px w-4 bg-gradient-to-r from-accent/30 to-slate-600/30" />
                )}
                <span
                  className={cn(
                    "text-[11px] font-semibold",
                    last ? "text-amber-200" : "text-slate-400",
                  )}
                >
                  {label}
                </span>
              </Fragment>
            );
          })}
        </div>

        {/* 右：迷你统计（深度层 3） */}
        <div className="absolute right-4 top-1/2 hidden -translate-y-1/2 items-center gap-2 lg:flex sm:right-6">
          {config.stats.map((stat, index) => (
            <div
              key={stat.label}
              ref={(node) => {
                statRefs.current[index] = node;
              }}
              className="rounded-lg border border-white/10 bg-white/5 px-2.5 py-1.5"
              style={{ willChange: "transform" }}
            >
              <p className="tabular text-[13px] font-extrabold leading-none text-white">
                {stat.value}
              </p>
              <p className="mt-1 text-[11px] leading-none text-slate-500">
                {stat.label}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
