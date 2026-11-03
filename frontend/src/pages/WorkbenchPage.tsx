import { BrainCircuit } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { FourBrainPanel } from "@/features/four-brain/FourBrainPanel";
import { LaunchReportPanel } from "@/features/four-brain/LaunchReportPanel";
import { ResearchPanel } from "@/features/workbench/ResearchPanel";
import { SellerMagicImportCard } from "@/features/workbench/SellerMagicImportCard";
import { AgentPageShell } from "@/widgets/AgentPageShell";
import { PageTurnTabs } from "@/shared/ui/page-turn-tabs";
import { RouteStatusBar } from "@/shared/motion/RouteStatusBar";

export default function WorkbenchPage() {
  const [searchParams] = useSearchParams();
  const activeTab = searchParams.get("tab") ?? "four-brain";

  return (
    <AgentPageShell
      icon={BrainCircuit}
      title="四脑协同选品工作台"
      description="市场、产品、风险、增长四角色独立分析，再按提示词综合输出可执行结论。"
    >
      <div className="entrance-reveal" style={{ animationDelay: "0.42s" }}>
        <RouteStatusBar
          items={[
            { label: "并行脑", value: "4 角色", tone: "cyan" },
            { label: "联网检索", value: "实时", tone: "green" },
            { label: "证据闸", value: "开启", tone: "amber" },
            { label: "输出", value: "综合报告", tone: "violet" },
          ]}
        />
      </div>
      <div className="entrance-reveal" style={{ animationDelay: "0.76s" }}>
        <PageTurnTabs
          key={activeTab}
          defaultValue={activeTab}
          listClassName="w-full justify-start overflow-x-auto"
          tabs={[
          {
            value: "four-brain",
            label: "四脑分析",
            content: <FourBrainPanel />,
          },
          {
            value: "launch-report",
            label: "立项报告",
            content: <LaunchReportPanel />,
          },
          {
            value: "research",
            label: "联网研究",
            content: <ResearchPanel />,
          },
          {
            value: "import",
            label: "数据接入",
            content: <SellerMagicImportCard />,
          },
          ]}
        />
      </div>
    </AgentPageShell>
  );
}
