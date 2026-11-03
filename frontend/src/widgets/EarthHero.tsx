import {
  ArrowRight,
  BrainCircuit,
  FileCheck2,
  Gauge,
  LayoutDashboard,
  Radio,
  ScrollText,
  ShieldCheck,
  Workflow,
} from "lucide-react";
import { Link } from "react-router-dom";
import { LogoMark } from "@/shared/brand/LogoMark";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { useTransitionNavigate } from "@/widgets/RouteTransition";

const painPoints = [
  {
    label: "政策突变难量化",
    path: "/trade?tab=policy-impact",
    icon: Gauge,
    accent: "text-amber-300",
  },
  {
    label: "结论依据不可追溯",
    path: "/trade?tab=report-policy",
    icon: FileCheck2,
    accent: "text-cyan-300",
  },
  {
    label: "黑盒指标不敢信",
    path: "/dashboard?tab=data-depth",
    icon: ScrollText,
    accent: "text-emerald-300",
  },
  {
    label: "结论难执行、换工具成本高",
    path: "/workbench?tab=import",
    icon: Workflow,
    accent: "text-violet-300",
  },
];

export function EarthHero() {
  const transitionNavigate = useTransitionNavigate();

  return (
    <section className="pointer-events-none relative z-10 flex min-h-[calc(100dvh-65px)] items-center px-4 py-14 sm:px-6">
      <div className="pointer-events-none mx-auto w-full max-w-[calc(100%-40px)] text-center md:max-w-[min(72vw,920px)]">
        <div className="mb-6 flex items-center justify-center gap-3">
          <LogoMark size={44} />
          <p className="text-sm font-bold tracking-[0.14em] text-cyan-300">
            远帆智品 · Trade Intelligence
          </p>
        </div>

        <h1 className="mx-auto max-w-[900px] text-center text-4xl font-extrabold leading-[1.08] text-white sm:text-5xl xl:text-6xl">
          可追溯的 Go/No-Go 选品决策
        </h1>

        <p className="text-gradient mt-3 block text-lg font-bold sm:text-xl xl:text-2xl">
          把销量趋势、关税政策、到岸成本与合规风险合并为可追溯的 Go/No-Go 决策
        </p>

        <p className="mt-3 text-xs font-semibold text-slate-400">
          卖什么 · 怎么卖 · 卖到哪 · 是否值得卖
        </p>

        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link
            to="/dashboard"
            className="pointer-events-auto"
            onClick={(event) => {
              event.preventDefault();
              transitionNavigate("/dashboard");
            }}
          >
            <Button size="lg">
              <LayoutDashboard className="h-4 w-4" />
              进入选品看板
              <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
          <Link
            to="/workbench"
            className="pointer-events-auto"
            onClick={(event) => {
              event.preventDefault();
              transitionNavigate("/workbench");
            }}
          >
            <Button variant="secondary" size="lg">
              <BrainCircuit className="h-4 w-4" />
              四脑工作台
            </Button>
          </Link>
        </div>

        <div className="mt-7 flex flex-wrap justify-center gap-2">
          <Badge tone="cyan">
            <Radio className="h-3.5 w-3.5" />
            每日联网快照
          </Badge>
          <Badge tone="green">
            <ShieldCheck className="h-3.5 w-3.5" />
            证据闸 · 官方源优先
          </Badge>
        </div>

        <p className="mt-9 text-[10px] font-bold tracking-[0.22em] text-slate-500 uppercase">
          痛点直击
        </p>
        <div className="pointer-events-auto mt-3 grid grid-cols-2 gap-2 text-left xl:grid-cols-4">
          {painPoints.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.label}
                type="button"
                onClick={() => transitionNavigate(item.path)}
                className="focus-ring group rounded-lg border border-white/10 bg-white/[0.045] p-3.5 text-left backdrop-blur-md transition-colors hover:border-accent/40 hover:bg-white/[0.08]"
                aria-label={item.label}
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="text-xs font-bold leading-5 text-white">{item.label}</p>
                  <Icon className={`h-4 w-4 shrink-0 ${item.accent}`} />
                </div>
                <ArrowRight className="mt-3 h-3.5 w-3.5 text-accent transition-transform group-hover:translate-x-0.5" />
              </button>
            );
          })}
        </div>
      </div>
    </section>
  );
}
