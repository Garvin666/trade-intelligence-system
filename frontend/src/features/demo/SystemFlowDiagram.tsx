import { Badge } from "@/shared/ui/badge";

interface SystemNode {
  id: string;
  x: number;
  label: string;
  sub: string;
  color: string;
}

export const SYSTEM_NODES: SystemNode[] = [
  {
    id: "sources",
    x: 100,
    label: "多源数据",
    sub: "Trends / 榜单 / 海关 / 政策",
    color: "#22D3EE",
  },
  {
    id: "platform",
    x: 300,
    label: "数据中台",
    sub: "清洗 / 特征 / 证据闸",
    color: "#38BDF8",
  },
  {
    id: "models",
    x: 500,
    label: "三模型预测",
    sub: "Prophet / LightGBM / StatsForecast",
    color: "#34D399",
  },
  {
    id: "recommend",
    x: 700,
    label: "六维推荐",
    sub: "需求 / 趋势 / 竞争 / 利润 / 合规 / 证据",
    color: "#F59E0B",
  },
  {
    id: "trade",
    x: 900,
    label: "贸易决策",
    sub: "关税 / 物流 / 合规 / IP",
    color: "#E879F9",
  },
  {
    id: "deliver",
    x: 1100,
    label: "交付",
    sub: "看板 / 四脑 / API / MCP",
    color: "#22D3EE",
  },
];

const EDGES = SYSTEM_NODES.slice(0, -1).map((node, index) => {
  const next = SYSTEM_NODES[index + 1];
  const from = node.x + 78;
  const to = next.x - 78;
  const mid = (from + to) / 2;
  return {
    id: `${node.id}-${next.id}`,
    path: `M ${from} 145 Q ${mid} 122 ${to} 145`,
    color: node.color,
  };
});

interface SystemFlowDiagramProps {
  animate?: boolean;
}

export function SystemFlowDiagram({ animate = true }: SystemFlowDiagramProps) {
  return (
    <div className="glass-strong p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-white">系统流程动画示意图</h2>
          <p className="mt-1 text-xs text-slate-400">数据包沿系统链路流动，展示本项目端到端能力</p>
        </div>
        <Badge tone="cyan">
          <span className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-cyan-300 opacity-60" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-cyan-300" />
          </span>
          系统在线
        </Badge>
      </div>

      <div className="scrollbar-thin overflow-x-auto pb-1">
        <svg
          viewBox="0 0 1200 260"
          className="h-auto min-w-[880px] w-full"
          role="img"
          aria-label="系统流程动画示意图"
        >
          <defs>
            <linearGradient id="flow-fade" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0" stopColor="rgba(34,211,238,.5)" />
              <stop offset=".5" stopColor="rgba(34,211,238,.08)" />
              <stop offset="1" stopColor="rgba(34,211,238,.5)" />
            </linearGradient>
          </defs>

          {EDGES.map((edge) => (
            <path
              key={edge.id}
              d={edge.path}
              fill="none"
              stroke="url(#flow-fade)"
              strokeWidth="2"
              strokeDasharray="5 5"
            />
          ))}

          {SYSTEM_NODES.map((node) => (
            <g key={node.id}>
              <rect
                x={node.x - 78}
                y={104}
                width={156}
                height={82}
                rx={14}
                fill="rgba(255,255,255,.06)"
                stroke={node.color}
                strokeOpacity=".35"
              />
              <rect
                x={node.x - 78}
                y={104}
                width={156}
                height={82}
                rx={14}
                fill="none"
                stroke="rgba(255,255,255,.12)"
                strokeOpacity=".25"
              />
              <circle cx={node.x} cy={130} r={5} fill={node.color} />
              <text
                x={node.x}
                y={156}
                textAnchor="middle"
                fill="#E8EEF6"
                fontSize="13"
                fontWeight="700"
              >
                {node.label}
              </text>
              <text
                x={node.x}
                y={174}
                textAnchor="middle"
                fill="#8FA3B8"
                fontSize="9"
              >
                {node.sub}
              </text>
            </g>
          ))}

          {animate &&
            EDGES.map((edge, index) => (
              <g key={`particle-${edge.id}`}>
                <circle r="4" fill={edge.color} opacity=".9">
                  <animateMotion
                    dur="2.6s"
                    repeatCount="indefinite"
                    path={edge.path}
                    begin={index % 2 === 0 ? "0s" : "1.3s"}
                  />
                </circle>
                <circle r="2" fill="#FFFFFF" opacity=".8">
                  <animateMotion
                    dur="2.6s"
                    repeatCount="indefinite"
                    path={edge.path}
                    begin={index % 2 === 0 ? "0.9s" : "2.1s"}
                  />
                </circle>
              </g>
            ))}
        </svg>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
        {SYSTEM_NODES.map((node, index) => (
          <span key={node.id} className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: node.color }} />
            {node.label}
            {index < SYSTEM_NODES.length - 1 && <span className="text-slate-700">→</span>}
          </span>
        ))}
      </div>
    </div>
  );
}
