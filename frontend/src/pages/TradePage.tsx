import { Ship } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { TradeDecisionPanel } from "@/features/trade-decision/TradeDecisionPanel";
import { PolicyImpactPanel } from "@/features/trade-decision/PolicyImpactPanel";
import { EvidenceLedgerPanel } from "@/features/trade-decision/EvidenceLedgerPanel";
import { HsCodePanel } from "@/features/trade-decision/HsCodePanel";
import { TradeReportPanel } from "@/features/trade-decision/TradeReportPanel";
import { TradeMarketComparePanel } from "@/features/trade-decision/TradeIntelPanels";
import { PlatformFitPanel } from "@/features/trade-decision/PlatformFitPanel";
import { ExportReportButton } from "@/features/dashboard/ExportReportButton";
import { AgentPageShell } from "@/widgets/AgentPageShell";
import { PageTurnTabs } from "@/shared/ui/page-turn-tabs";
import { RouteStatusBar } from "@/shared/motion/RouteStatusBar";

export default function TradePage() {
  const [searchParams] = useSearchParams();
  const activeTab = searchParams.get("tab") ?? "decision";

  return (
    <AgentPageShell
      icon={Ship}
      title="贸易决策工作台"
      description="围绕卖什么、怎么卖、卖到哪、是否值得卖：本地规则引擎给出可追溯的关税、合规、利润与 Go/No-Go 决策，AI 接入再生成综合解读。"
      action={
        <ExportReportButton
          filters={{}}
          conclusion="基于贸易决策工作台当前参数生成的决策报告。"
        />
      }
    >
      <div className="entrance-reveal" style={{ animationDelay: "0.42s" }}>
        <RouteStatusBar
          items={[
            { label: "HS Code", value: "六位速查", tone: "cyan" },
            { label: "关税成本", value: "到岸测算", tone: "amber" },
            { label: "利润测算", value: "敏感性", tone: "green" },
            { label: "合规雷达", value: "官方源", tone: "violet" },
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
            value: "decision",
            label: "贸易决策",
            content: (
              <div className="grid gap-4">
                <TradeDecisionPanel />
                <HsCodePanel />
              </div>
            ),
          },
          {
            value: "policy-impact",
            label: "政策冲击",
            content: <PolicyImpactPanel />,
          },
          {
            value: "market-compare",
            label: "市场与平台",
            content: (
              <div className="grid gap-4">
                <TradeMarketComparePanel />
                <PlatformFitPanel />
              </div>
            ),
          },
          {
            value: "report-policy",
            label: "报告与证据",
            content: (
              <div className="grid gap-4">
                <TradeReportPanel />
                <EvidenceLedgerPanel />
              </div>
            ),
          },
          ]}
        />
      </div>
    </AgentPageShell>
  );
}
