import { ServerCog } from "lucide-react";
import { SystemConsole } from "@/features/system/SystemConsole";
import { AgentPageShell } from "@/widgets/AgentPageShell";
import { Page3DScene } from "@/shared/motion/Page3DScene";

export default function SystemPage() {
  return (
    <AgentPageShell
      icon={ServerCog}
      title="系统控制台"
      description="统一管理后端状态、后台任务、真实能力对接、AI 接入、反馈权重与顶级 AI 对照。"
    >
      <div className="entrance-reveal" style={{ animationDelay: "0.68s" }}>
        <Page3DScene className="mb-6" height={132} />
      </div>
      <SystemConsole />
    </AgentPageShell>
  );
}
