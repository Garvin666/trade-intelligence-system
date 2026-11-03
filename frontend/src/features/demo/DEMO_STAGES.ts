import {
  Boxes,
  Cpu,
  Database,
  Filter,
  Gauge,
  Ship,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";

export interface DemoStage {
  id: string;
  label: string;
  description: string;
  metric: string;
  icon: LucideIcon;
}

export const DEMO_STAGES: DemoStage[] = [
  {
    id: "collect",
    label: "多源采集",
    description: "Google Trends / 平台榜单 / 海关出口 / 政策官方源",
    metric: "132 品类 × 15 市场",
    icon: Database,
  },
  {
    id: "clean",
    label: "数据清洗",
    description: "去重、缺失处理、口径统一，保持可复现",
    metric: "205,920 行周度记录",
    icon: Filter,
  },
  {
    id: "feature",
    label: "特征工程",
    description: "趋势、季节、竞争、政策信号进入特征面板",
    metric: "多维特征向量",
    icon: Boxes,
  },
  {
    id: "train",
    label: "三模型训练",
    description: "Prophet / LightGBM / StatsForecast 独立基线",
    metric: "MAPE 横向对比",
    icon: Cpu,
  },
  {
    id: "forecast",
    label: "90 天预测",
    description: "未来销量与置信区间滚动更新",
    metric: "356,400 条预测",
    icon: TrendingUp,
  },
  {
    id: "recommend",
    label: "六维评分",
    description: "需求、趋势、竞争、利润、合规、证据",
    metric: "Top 20 推荐",
    icon: Gauge,
  },
  {
    id: "decide",
    label: "贸易决策",
    description: "关税、物流、合规、IP、融资就绪度",
    metric: "Go / No-Go",
    icon: Ship,
  },
];
