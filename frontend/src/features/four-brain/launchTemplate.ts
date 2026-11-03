export type LaunchFieldKey =
  | "market"
  | "category"
  | "product"
  | "competitors"
  | "reviews"
  | "costs"
  | "keywords";

export type LaunchSectionKey =
  | "summary"
  | "market"
  | "competitors"
  | "pain_points"
  | "product"
  | "finance"
  | "plan"
  | "risk";

export type LaunchStyle = "logic" | "brief" | "strategy";
export type LaunchOutputFormat = "markdown" | "checklist" | "table";

export interface LaunchFields {
  market: string;
  market_custom?: string;
  category: string;
  category_custom?: string;
  product: string;
  competitors: string;
  reviews: string;
  costs: string;
  keywords: string;
  sections: LaunchSectionKey[];
  style: LaunchStyle;
  output_format: LaunchOutputFormat;
}

export const LAUNCH_FIELD_ORDER: LaunchFieldKey[] = [
  "market",
  "category",
  "product",
  "competitors",
  "reviews",
  "costs",
  "keywords",
];

export const LAUNCH_FIELD_LABELS: Record<LaunchFieldKey, string> = {
  market: "目标市场",
  category: "目标类目",
  product: "候选产品",
  competitors: "竞品数据",
  reviews: "评论分析",
  costs: "成本数据",
  keywords: "关键词数据",
};

export const LAUNCH_SECTIONS: Array<{
  value: LaunchSectionKey;
  label: string;
  description: string;
}> = [
  { value: "summary", label: "执行摘要", description: "一句话结论、决策逻辑与关键指标" },
  { value: "market", label: "市场吸引力", description: "市场体量、结构、趋势判断" },
  { value: "competitors", label: "竞品格局", description: "竞品画像、拆解与空白位" },
  { value: "pain_points", label: "用户痛点", description: "评论聚类、优先级矩阵与产品动作" },
  { value: "product", label: "产品方案", description: "产品定义、质量门槛与成本控制" },
  { value: "finance", label: "财务模型", description: "基准情景、压力测试与盈亏平衡" },
  { value: "plan", label: "上市验证", description: "90 天阶段计划与退出条件" },
  { value: "risk", label: "风险清单", description: "风险预警、缓解动作与最终门槛" },
];

export const LAUNCH_STYLES: Array<{ value: LaunchStyle; label: string }> = [
  { value: "logic", label: "逻辑版" },
  { value: "brief", label: "精简版" },
  { value: "strategy", label: "策略版" },
];

export const LAUNCH_OUTPUT_FORMATS: Array<{
  value: LaunchOutputFormat;
  label: string;
}> = [
  { value: "markdown", label: "Markdown 报告" },
  { value: "checklist", label: "Check-List" },
  { value: "table", label: "表格摘要" },
];

const SECTION_PROMPTS: Record<LaunchSectionKey, string> = {
  summary: `### 1. 执行摘要
- **一句话结论**：判断是 Go / No-Go / 条件式进入。
- **核心决策逻辑**：用 3-5 个要点概括需求、竞争、利润、风险。
- **关键指标卡片**：综合评分、建议零售价、预期利润率、头部集中度。`,
  market: `### 2. 市场吸引力分析
- **市场体量**：Top 30 月销量、月销售额、同比增长率。
- **市场结构**：平均售价、价格带分布、头部集中度（CR10）、新品存活率。
- **趋势判断**：蓝海 / 红海 / 细分机会及依据。`,
  competitors: `### 3. 竞品格局与空白位
- **竞品画像**：匿名化表格列出主要竞争对手。
- **竞品拆解**：头部竞品共同优势与系统性弱点。
- **空白位识别**：功能空白、体验空白、内容空白。`,
  pain_points: `### 4. 用户需求与痛点优先级
- **评论聚类分析**：负面反馈按频次排序并计算占比。
- **优先级矩阵**：P0 / P1 / P2 分级。
- **产品动作映射**：针对每个痛点提出产品设计改进方案。`,
  product: `### 5. 产品方案与质量门槛
- **产品定义**：尺寸、颜色、材质、附件。
- **硬指标门槛**：必须通过的测试标准。
- **成本控制**：BOM 成本拆解与到岸价上限红线。`,
  finance: `### 6. 财务模型与情景测算
- **基准情景**：收入、成本、佣金、物流、广告摊销后的单位贡献利润与利润率。
- **压力测试**：降价、成本上涨、广告效率变差三种情景。
- **盈亏平衡**：特定 ACOS 下的保本点。`,
  plan: `### 7. 上市验证与执行计划（90天）
- **阶段划分**：样品验证 -> 上市准备 -> 小规模发布 -> 扩量优化 -> 复盘决策。
- **关键动作**：每个阶段的具体操作。
- **退出条件（No-Go Triggers）**：明确数据不达标时应暂停项目。`,
  risk: `### 8. 风险清单与最终门槛
- **风险清单**：低价竞争、供应链不稳、合规风险等。
- **预警信号与缓解动作**。
- **最终 Go / No-Go 门槛**：以 Check-List 形式呈现。`,
};

const STYLE_NOTES: Record<LaunchStyle, string> = {
  logic: "专业中文，夹杂必要英文术语，客观、理性、数据驱动，每个章节末尾给出结论或行动建议。",
  brief: "精简表达，每章不超过 5 条要点，只保留直接影响 Go / No-Go 的信息。",
  strategy: "偏经营策略，补充优先级排序、资源投入建议与多阶段节奏。",
};

export const LAUNCH_TEMPLATE = `# Role: 跨境电商选品与竞品分析专家

你是一位拥有5年以上亚马逊选品经验的资深产品经理，擅长通过结构化数据分析和逻辑推导做出立项决策。分析风格严谨、克制，不盲目乐观，以"先验证后放量"为核心原则。

## Task
请根据我提供的以下数据，生成一份完整的《选品立项分析报告》：

## Input Data
- **目标市场**：{{market}}
- **目标类目**：{{category}}
- **候选产品**：{{product}}
- **竞品数据**：{{competitors}}
- **评论分析**：{{reviews}}
- **成本数据**：{{costs}}
- **关键词数据**：{{keywords}}

## Output Format
- 报告风格：{{style}}
- 输出结构：{{output_format}}
- 请按以下勾选章节生成：

{{sections}}

## Tone & Style
{{style_note}}

## Initialization
请以 "**Codex 直出（逻辑版）**" 作为报告开头，并开始分析。`;

export const LAUNCH_EXAMPLE: LaunchFields = {
  market: "us",
  market_custom: "Amazon 美国站",
  category: "cn_latiao",
  category_custom: "Grocery & Gourmet Food > Snacks > Spicy Strips",
  product: "辣条（网红休闲零食）",
  competitors:
    "竞品 A：售价 $4.99、评分 4.6、评论数约 2,400、月销约 6,800，核心卖点“麻辣过瘾、独立小包装”；竞品 B：售价 $6.49、评分 4.3、评论数约 1,100、月销约 2,600，核心卖点“低钠配方、配料表干净”。示例数据，需替换为实际调研结果。",
  reviews:
    "好评关键词聚类：够辣、口感筋道、分量足、复购；差评关键词聚类：过油、偏咸、包装漏气、运输压碎。示例聚类，需替换。",
  costs:
    "采购价 ¥12/件（100g 装）、头程运费 ¥1.8/件、关税按 HS 1905 计征、美国 800 美元免税额内为 0。示例数据，需替换。",
  keywords:
    "核心词 latiao spicy strips：月搜索量约 12,000、CPC 约 $0.42；长尾词 chinese spicy snack：月搜索量约 8,800、CPC 约 $0.35。示例数据，需替换。",
  sections: [
    "summary",
    "market",
    "competitors",
    "pain_points",
    "product",
    "finance",
    "plan",
    "risk",
  ],
  style: "logic",
  output_format: "markdown",
};

export const LAUNCH_EXAMPLES: LaunchFields[] = [
  LAUNCH_EXAMPLE,
  {
    market: "eu",
    market_custom: "Amazon 欧洲站（DE）",
    category: "cn_longjing",
    category_custom: "Grocery > Tea > Green Tea",
    product: "西湖龙井（明前绿茶）",
    competitors: "竞品以 50-100g 礼盒装绿茶为主，售价 18-35 欧元，主打产地区分与有机认证。示例数据，需替换。",
    reviews: "差评集中在香气流失、包装密封性与欧盟农残标准说明不足。示例数据，需替换。",
    costs: "采购价 ¥96/盒（100g）、头程 ¥6/盒、VAT 19%、农残检测费另计。示例数据，需替换。",
    keywords: "longjing green tea：月搜索量约 9,500；loose leaf green tea：月搜索量约 22,000。示例数据，需替换。",
    sections: ["summary", "market", "competitors", "pain_points", "finance", "risk"],
    style: "brief",
    output_format: "checklist",
  },
];

export function buildLaunchPrompt(fields: LaunchFields, template: string): string {
  const market = fields.market_custom?.trim() || fields.market || "（请补充目标市场）";
  const category = fields.category_custom?.trim() || fields.category || "（请补充目标类目）";
  const sections = LAUNCH_SECTIONS.filter((section) => fields.sections.includes(section.value))
    .map((section) => SECTION_PROMPTS[section.value])
    .join("\n\n");
  const outputFormat = LAUNCH_OUTPUT_FORMATS.find(
    (item) => item.value === fields.output_format,
  )?.label ?? "Markdown 报告";
  const style = LAUNCH_STYLES.find((item) => item.value === fields.style)?.label ?? "逻辑版";
  const prompt = template
    .replaceAll("{{market}}", market)
    .replaceAll("{{category}}", category)
    .replaceAll("{{product}}", fields.product?.trim() || "（请补充候选产品）")
    .replaceAll("{{competitors}}", fields.competitors?.trim() || "（请补充竞品数据）")
    .replaceAll("{{reviews}}", fields.reviews?.trim() || "（请补充评论分析）")
    .replaceAll("{{costs}}", fields.costs?.trim() || "（请补充成本数据）")
    .replaceAll("{{keywords}}", fields.keywords?.trim() || "（请补充关键词数据）")
    .replaceAll("{{sections}}", sections || "（未选择章节，请选择至少一个章节）")
    .replaceAll("{{style}}", style)
    .replaceAll("{{output_format}}", outputFormat)
    .replaceAll("{{style_note}}", STYLE_NOTES[fields.style]);
  return prompt.trim();
}
