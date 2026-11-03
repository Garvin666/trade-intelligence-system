---
name: cross-border-selection-decision
description: 跨境电商智能选品决策：推荐、贸易决策、HS 速查与证据闸。用于向 AI 助手提供可调用的选品决策能力。
---

# 跨境电商智能选品决策

本项目提供统一后端 API，AI 助手可直接调用以下只读接口：

- `GET /api/recommendations?top=10`：Top N 选品推荐，返回综合评分、六维评分、Go/No-Go 判定与推荐理由。
- `GET /api/trade/decision?category=pet&market=us&unit_price_usd=22&procurement_cost_cny=55`：单组合完整贸易决策，包含到岸成本、合规、HS 速查、卖前体检与尽调清单。
- `GET /api/trade/hs-code?category=pet&market=us`：品类默认 HS6 码与基础税率速查。
- `GET /api/search/trends?category=pet&market=us`：多源热度趋势。
- `GET /api/data/status`：数据更新状态，包含每日联网快照、Google Trends、平台榜单、市场日报与货源/供应商状态。
- `GET /api/data/suppliers`：最新货源/供应商尽调快照与状态。

## 使用规则

1. 数值一律来自模型与统计产物，AI 只做解释与建议，不得生成数值。
2. 引用行业事实前必须满足证据闸：有来源、日期/链接、状态（已检索/待核实/模拟）。
3. 回退或模拟数据必须明确标注，不得伪装成真实数据。
4. 离线演示无 Key 也可运行；联网能力通过环境变量开关启用。
