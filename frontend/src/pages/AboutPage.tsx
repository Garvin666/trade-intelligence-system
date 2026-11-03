import { BadgeCheck, Boxes, Cpu, FlaskConical, Info, Radar, Workflow } from "lucide-react";
import { GlassCard } from "@/shared/ui/glass-card";
import { Page3DScene } from "@/shared/motion/Page3DScene";
import { AgentPageShell } from "@/widgets/AgentPageShell";

const features = [
  { icon: Boxes, title: "132 品类 × 15 市场", desc: "1980 组组合覆盖主要跨境销售场景" },
  { icon: Cpu, title: "三模型预测", desc: "Prophet / LightGBM / StatsForecast 独立基线" },
  { icon: FlaskConical, title: "证据闸", desc: "官方原文优先，无法核实条目显式标注" },
  { icon: Radar, title: "政策雷达", desc: "gov.cn / Federal Register / 欧盟 / GOV.UK" },
  { icon: BadgeCheck, title: "自动化测试", desc: "464 项 pytest 覆盖数据、API 与决策链路" },
  { icon: Workflow, title: "统一后端", desc: "FastAPI + MCP + 后台任务单进程运行" },
];

export default function AboutPage() {
  return (
    <AgentPageShell
      icon={Info}
      title="远帆智品 · 贸易决策智能"
      description="面向中国跨境卖家的贸易决策智能平台：把销量趋势、关税政策、到岸成本与合规风险合并为可追溯的 Go/No-Go 决策。"
    >
      <div className="entrance-reveal" style={{ animationDelay: "0.52s" }}>
        <Page3DScene className="mb-6" height={132} />
      </div>
      <div className="entrance-reveal grid gap-4 sm:grid-cols-2 lg:grid-cols-3" style={{ animationDelay: "0.68s" }}>
        {features.map((feature) => (
          <GlassCard key={feature.title} className="p-5">
            <feature.icon className="h-6 w-6 text-accent" />
            <h2 className="mt-4 text-sm font-bold text-white">{feature.title}</h2>
            <p className="mt-1.5 text-xs leading-5 text-slate-400">{feature.desc}</p>
          </GlassCard>
        ))}
      </div>
    </AgentPageShell>
  );
}
