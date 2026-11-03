import { ArrowRight, BadgeCheck, BrainCircuit, Package, Ship } from "lucide-react";
import { useTransitionNavigate } from "@/widgets/RouteTransition";
import { FourQuestionsMark } from "@/shared/brand/FourQuestionsMark";
import { GlassCard } from "@/shared/ui/glass-card";
import { Button } from "@/shared/ui/button";

const questions = [
  {
    key: "卖什么",
    title: "选品看板",
    desc: "132 品类 × 15 市场，六维评分与 Go/No-Go 判定，回答选什么值得做。",
    path: "/dashboard",
    icon: Package,
    tone: "cyan",
  },
  {
    key: "怎么卖",
    title: "四脑工作台",
    desc: "战略、市场、产品、风险四角色并行分析，按提示词综合输出立项建议。",
    path: "/workbench",
    icon: BrainCircuit,
    tone: "emerald",
  },
  {
    key: "卖到哪",
    title: "贸易决策",
    desc: "HS Code、关税成本、利润测算与市场择优，确定目的地与销售策略。",
    path: "/trade",
    icon: Ship,
    tone: "amber",
  },
  {
    key: "是否值得卖",
    title: "证据闸裁决",
    desc: "官方源优先、证据闸与裁决机制，回答投入产出是否值得继续。",
    path: "/dashboard",
    icon: BadgeCheck,
    tone: "slate",
  },
];

export function FourQuestionsGuide() {
  const transitionNavigate = useTransitionNavigate();
  return (
    <section className="relative border-t border-white/8 bg-base" aria-label="远帆四问导览">
      <div className="mx-auto max-w-[1440px] px-4 py-16 sm:px-6 lg:py-24">
        <div className="mb-10 flex flex-wrap items-end justify-between gap-6">
          <div className="flex items-center gap-4">
            <FourQuestionsMark size={54} labelClassName="hidden" className="text-slate-300" />
            <div>
              <p className="text-[11px] font-bold tracking-[.16em] text-accent uppercase">
                远帆四问
              </p>
              <h2 className="mt-1 text-2xl font-extrabold text-white">
                从一条航线的四个问题出发
              </h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-400">
                每个问题都对应一条真实业务链路，从数据到决策全程可追溯。
              </p>
            </div>
          </div>
          <Button variant="outline" onClick={() => transitionNavigate("/dashboard")}>
            进入选品看板
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {questions.map((item) => {
            const Icon = item.icon;
            return (
              <div
                key={item.key}
                role="button"
                tabIndex={0}
                onClick={() => transitionNavigate(item.path)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    transitionNavigate(item.path);
                  }
                }}
                className="focus-ring group cursor-pointer text-left"
              >
                <GlassCard className="h-full transition-colors group-hover:border-white/20">
                  <div className="mb-4 flex items-center justify-between">
                    <span
                      className={
                        item.tone === "cyan"
                          ? "text-accent"
                          : item.tone === "emerald"
                            ? "text-emerald-300"
                            : item.tone === "amber"
                              ? "text-amber-300"
                              : "text-slate-300"
                      }
                    >
                      <Icon className="h-6 w-6" />
                    </span>
                    <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] font-bold text-slate-300">
                      {item.key}
                    </span>
                  </div>
                  <h3 className="text-base font-extrabold text-white">{item.title}</h3>
                  <p className="mt-2 text-xs leading-5 text-slate-400">{item.desc}</p>
                  <span className="mt-4 inline-flex items-center gap-1 text-xs font-semibold text-accent">
                    查看
                    <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
                  </span>
                </GlassCard>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
