import {
  ArrowRight,
  BrainCircuit,
  LayoutDashboard,
  MonitorPlay,
  Radio,
  ShieldCheck,
} from "lucide-react";
import { useRef } from "react";
import { gsap } from "gsap";
import { useGSAP } from "@gsap/react";
import { Link } from "react-router-dom";
import { useTransitionNavigate } from "@/widgets/RouteTransition";
import { LogoMark } from "@/shared/brand/LogoMark";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { Page3DScene } from "@/shared/motion/Page3DScene";
import { InteractiveMaritimeScene } from "@/shared/motion/InteractiveMaritimeScene";

interface HeroPanelProps {
  /** fullscreen = 首页全屏星空背景；deck = 演示播片内的双栏卡片版 */
  layout?: "fullscreen" | "deck";
  /** fullscreen 模式下显示“播片演示”入口 */
  onOpenDemoDeck?: () => void;
}

export function HeroPanel({
  layout = "fullscreen",
  onOpenDemoDeck,
}: HeroPanelProps) {
  const transitionNavigate = useTransitionNavigate();
  const sectionRef = useRef<HTMLElement | null>(null);
  const fullscreen = layout === "fullscreen";

  useGSAP(
    () => {
      if (!fullscreen) return;
      const mm = gsap.matchMedia();
      mm.add("(prefers-reduced-motion: reduce)", () => {
        gsap.set("[data-hero-enter]", { clearProps: "all" });
      });
      mm.add("(prefers-reduced-motion: no-preference)", () => {
        gsap.fromTo(
          "[data-hero-enter]",
          { autoAlpha: 0, y: 16 },
          {
            autoAlpha: 1,
            y: 0,
            duration: 0.7,
            ease: "power2.out",
            stagger: 0.09,
            delay: 0.12,
          },
        );
      });
      return () => mm.revert();
    },
    { scope: sectionRef, dependencies: [fullscreen] },
  );

  const renderCopy = () => (
    <div>
      <div className="mb-5 flex items-center gap-2.5" data-hero-enter>
        <LogoMark size={38} />
        <div>
          <p className="text-[11px] font-bold tracking-[.2em] text-accent uppercase">
            Trade Intelligence
          </p>
          <p className="text-xs text-slate-400">贸易决策智能</p>
        </div>
      </div>
      <h1
        className="text-3xl font-extrabold leading-[1.08] text-white sm:text-4xl xl:text-5xl"
        data-hero-enter
      >
        远帆智品
        <span className="text-gradient mt-2 block text-lg font-bold sm:text-xl xl:text-[24px]">
          把销量趋势、关税政策、到岸成本与合规风险合并为可追溯的 Go/No-Go 决策
        </span>
      </h1>
      <p
        className="mt-3 text-xs font-semibold text-slate-400"
        data-hero-enter
      >
        卖什么 · 怎么卖 · 卖到哪 · 是否值得卖
      </p>
      <p
        className="hero-copy-gradient mt-4 max-w-[56ch] text-sm leading-6 sm:text-base sm:leading-7"
        data-hero-enter
      >
        面向中国跨境卖家的贸易决策智能平台：在备货前判断卖什么、卖到哪、是否值得卖，
        从趋势预测、政策事件、到岸成本到合规风险全程可追溯。
      </p>
      <div className="mt-6 flex flex-wrap items-center gap-2.5" data-hero-enter>
        <Link
          to="/dashboard"
          onClick={(event) => {
            event.preventDefault();
            transitionNavigate("/dashboard");
          }}
        >
          <Button>
            <LayoutDashboard className="h-4 w-4" />
            进入选品看板
            <ArrowRight className="h-4 w-4" />
          </Button>
        </Link>
        <Link
          to="/workbench"
          onClick={(event) => {
            event.preventDefault();
            transitionNavigate("/workbench");
          }}
        >
          <Button variant="secondary">
            <BrainCircuit className="h-4 w-4" />
            四脑工作台
          </Button>
        </Link>
        {onOpenDemoDeck && (
          <Button variant="outline" onClick={onOpenDemoDeck}>
            <MonitorPlay className="h-4 w-4" />
            播片演示
          </Button>
        )}
      </div>
      <div className="mt-6 flex flex-wrap gap-2" data-hero-enter>
        <Badge tone="cyan">
          <Radio className="h-3.5 w-3.5" />
          每日联网快照
        </Badge>
        <Badge tone="green">
          <ShieldCheck className="h-3.5 w-3.5" />
          证据闸与官方源优先
        </Badge>
        <Badge tone="amber">
          <ShieldCheck className="h-3.5 w-3.5" />
          可追溯 Go/No-Go
        </Badge>
      </div>
    </div>
  );

  if (layout === "fullscreen") {
    return (
      <section
        ref={sectionRef}
        className="relative isolate min-h-[calc(100dvh-64px)] overflow-hidden bg-base"
        aria-label="远帆智品首页"
      >
        <InteractiveMaritimeScene
          fullscreen
          variant="default"
        />
        <div className="pointer-events-none absolute inset-0 z-[2] bg-[linear-gradient(90deg,rgba(6,10,19,.94)_0%,rgba(6,10,19,.72)_30%,rgba(6,10,19,.18)_62%,transparent_84%)]" />
        <div className="pointer-events-none absolute inset-x-0 bottom-0 z-[2] h-44 bg-[linear-gradient(180deg,transparent,rgba(6,10,19,.92))] lg:hidden" />
        <div className="pointer-events-none relative z-10 mx-auto flex min-h-[calc(100dvh-64px)] max-w-[1440px] items-end px-4 pb-16 sm:px-6 lg:pb-20">
          <div className="pointer-events-auto w-full max-w-2xl">
            {renderCopy()}
          </div>
        </div>
      </section>
    );
  }

  return (
    <section ref={sectionRef} className="hero-bg min-h-[calc(100dvh-64px)]">
      <div className="mx-auto grid max-w-[1440px] gap-8 px-4 py-10 sm:px-6 lg:grid-cols-[minmax(0,.78fr)_minmax(0,1.22fr)] lg:items-center lg:gap-10 lg:py-14">
        <div className="max-w-2xl">{renderCopy()}</div>
        <Page3DScene
          height={520}
          className="h-[480px] lg:h-[calc(100dvh-190px)] lg:max-h-[640px] lg:min-h-[520px]"
        />
      </div>
    </section>
  );
}
