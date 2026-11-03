import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  BrainCircuit,
  Gauge,
  PlugZap,
  ServerCog,
  ShieldCheck,
  SlidersHorizontal,
} from "lucide-react";
import { AiConfigPanel } from "@/features/ai-config/AiConfigPanel";
import { IntegrationPanel } from "@/features/plans/IntegrationPanel";
import { fetchEnvCheck } from "@/shared/api/client";
import { IS_OFFLINE } from "@/shared/api/offline";
import { GlassCard } from "@/shared/ui/glass-card";
import { PageTurnTabs } from "@/shared/ui/page-turn-tabs";
import { ControlBenchmarkPanel } from "./ControlBenchmarkPanel";
import { EnvCheckPanel } from "./EnvCheckPanel";
import { FeedbackWeightsPanel } from "./FeedbackWeightsPanel";
import { JobsPanel } from "./JobsPanel";
import { SystemOverview } from "./SystemOverview";

export function SystemConsole() {
  const queryClient = useQueryClient();

  // 进入系统控制台即预取环境自检，避免首次切换到"环境自检"页签时空白等待
  useEffect(() => {
    if (IS_OFFLINE) return;
    void queryClient.prefetchQuery({
      queryKey: ["env-check", IS_OFFLINE],
      queryFn: () => fetchEnvCheck(),
      staleTime: 30_000,
    });
  }, [queryClient]);

  return (
    <div className="grid gap-4">
      {IS_OFFLINE && (
        <GlassCard>
          <p className="text-sm text-amber-200">
            当前为离线单文件模式：系统控制台仅展示离线快照，在线功能需要启动 FastAPI 后端后刷新页面。
          </p>
        </GlassCard>
      )}
      <PageTurnTabs
        defaultValue="overview"
        listClassName="w-full justify-start overflow-x-auto"
        tabs={[
          {
            value: "overview",
            label: (
              <>
                <Activity className="mr-1.5 h-3.5 w-3.5" />
                概览
              </>
            ),
            content: <SystemOverview />,
          },
          {
            value: "capabilities",
            label: (
              <>
                <PlugZap className="mr-1.5 h-3.5 w-3.5" />
                真实能力
              </>
            ),
            content: <IntegrationPanel showSystemLink={false} />,
          },
          {
            value: "jobs",
            label: (
              <>
                <ServerCog className="mr-1.5 h-3.5 w-3.5" />
                后台任务
              </>
            ),
            content: <JobsPanel />,
          },
          {
            value: "ai",
            label: (
              <>
                <BrainCircuit className="mr-1.5 h-3.5 w-3.5" />
                AI 接入
              </>
            ),
            content: (
              <GlassCard
                title="AI 接入"
                description="统一模型与搜索配置，同时写入后端内存与浏览器"
              >
                <AiConfigPanel />
              </GlassCard>
            ),
          },
          {
            value: "feedback",
            label: (
              <>
                <SlidersHorizontal className="mr-1.5 h-3.5 w-3.5" />
                反馈与权重
              </>
            ),
            content: <FeedbackWeightsPanel />,
          },
          {
            value: "control",
            label: (
              <>
                <Gauge className="mr-1.5 h-3.5 w-3.5" />
                AI 对照
              </>
            ),
            content: <ControlBenchmarkPanel />,
          },
          {
            value: "check",
            label: (
              <>
                <ShieldCheck className="mr-1.5 h-3.5 w-3.5" />
                环境自检
              </>
            ),
            content: <EnvCheckPanel />,
          },
        ]}
      />
    </div>
  );
}
