# 顶级 AI 对照组运行说明

本项目用同一份训练数据、同一套提示词，让“AI 接入”中配置的 OpenAI 兼容模型独立完成“趋势洞察 + 12 周销量预测 + Top 5 选品建议”，并统一评分。自真实特征增强重训接入后，`train_data.csv` 由 `data/processed/clean_data_real.csv` 按最近 12 周切分生成，除原始市场指标外还包含本地真实数据集聚合出的特征列。

## 文件

| 文件 | 说明 |
|------|------|
| `train_data.csv` | 发给评测模型的训练数据（690 组合 × 92 周，截至 2026-05-21） |
| `holdout_data.csv` | 隐藏测试集（690 组合 × 12 周 = 8280 格，2026-05-28 至 2026-08-13），只用于评分，绝不发给模型 |
| `prompt.md` | 统一提示词 |
| `responses/global/run{1,2}.md` | 评测模型的原始回复（API 自动写入） |
| `responses/global/run{1,2}.meta.json` | 运行元数据（模型 ID、Base URL、时间等） |

## 第一步：切分数据

```powershell
python scripts\control_group.py prepare
```

## 第二步：主 Demo 页面运行（推荐）

1. 启动后端并打开主 Demo，进入“检验测试中心”>“顶级 AI 对照”。
2. 在顶部“AI 接入”中填写 API Key、Base URL 与模型，保存并全局生效。
3. 默认“轻量模式”跑固定 12 组合（2 次调用，约 1-3 分钟）；勾选“完整分批（8280 格）”后按 15 个市场分批运行完整 690 组合（30 次调用，耗时更长）。
4. 点击“运行 AI 对照”，系统自动评分并写入 `output/control/control_metrics.json`，结果按实际口径（轻量 144 格或完整 8280 格）展示。

## 第三步：命令行运行

```powershell
# 使用环境变量（OpenAI 兼容）
$env:OPENAI_API_KEY="..."
$env:OPENAI_BASE_URL="https://api.example.com/v1"
$env:OPENAI_MODEL="your-model"
python scripts\control_group.py run --global

# 或直接传参
python scripts\control_group.py run --global --api-key "..." --base-url "https://api.example.com/v1" --model-id "your-model" --runs 2

# 指定对照口径：lite=12 组合轻量（默认），full=按市场分批完整 8280 格
python scripts\control_group.py run --global --mode full
```

## 第四步：评分

```powershell
python scripts\control_group.py score
```

结果输出到 `output/control/score_summary.md` 与 `output/control/control_metrics.json`；每个模型条目包含 `label`、`api_model_id`、`base_url`、`source`，结果表显示真实模型名。

## 旧版兼容

旧 `control_group.py web` 与 `/api/control/web/*`（DeepSeek 网页版粘贴评分）保留为兼容入口，主 Demo 页面不再展示。

## 协议提醒

- 运行前先执行 `scripts/backfill_control_real.py`，确认 `output/control/github_signals.json` 与 `output/control/github_real_results.csv` 已生成。
- AI 回复必须包含 `核心洞察`、`未来 12 周销量预测`、`Top 5 选品建议`、`方法与不确定性` 四段；缺段自动重跑最多 3 次，仍缺则标记失败且不进入有效指标。
- 评测模型标准跑 2 次；个别环境无法重复时允许 1 次并在报告注明。
- 保持单轮提问，不要给模型任何纠错或提示。
- 评分中“幻觉待核验”是未在原始数据中直接匹配到的数字候选，需要人工复核是派生统计还是编造。
