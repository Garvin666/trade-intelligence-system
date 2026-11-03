import { Bot } from "lucide-react";
import { SmartAgentChat } from "@/features/smart-agent/SmartAgentChat";
import { IS_OFFLINE } from "@/shared/api/offline";
import { RouteStatusBar } from "@/shared/motion/RouteStatusBar";
import { AgentPageShell } from "@/widgets/AgentPageShell";

export default function AgentPage() {
  if (IS_OFFLINE) {
    return (
      <AgentPageShell icon={Bot} title="小助手" description="自然语言指令 · 分步执行 · 写操作先确认">
        <p className="text-sm text-slate-400">小助手需要在线后端，离线模式不可用。</p>
      </AgentPageShell>
    );
  }
  return (
    <AgentPageShell
      icon={Bot}
      title="小助手"
      description="自然语言指令 · 分步执行 · 写操作先确认"
    >
      <div className="entrance-reveal" style={{ animationDelay: "0.42s" }}>
        <RouteStatusBar
          className="mb-6"
          items={[
            { label: "会话", value: "在线", tone: "green" },
            { label: "工具", value: "get_market_info", tone: "cyan" },
            { label: "传输", value: "SSE", tone: "violet" },
            { label: "鉴权", value: "JWT", tone: "amber" },
          ]}
        />
      </div>
      <SmartAgentChat />
    </AgentPageShell>
  );
}
