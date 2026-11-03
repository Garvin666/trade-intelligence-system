"""从 output/datasets_inventory.json 生成统一数据集索引 Markdown。

用法：
    python scripts\\build_datasets_inventory.py    # 先生成 inventory JSON
    python scripts\\build_datasets_index.py        # 再生成 Markdown 索引
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

INVENTORY = PROJECT_ROOT / "output" / "datasets_inventory.json"
INDEX_MD = PROJECT_ROOT / "data" / "DATASETS_INDEX.md"
INDEX_JSON = PROJECT_ROOT / "data" / "datasets_manifest.json"


def main() -> int:
    if not INVENTORY.exists():
        print(f"缺少 {INVENTORY}，请先运行 scripts\\build_datasets_inventory.py")
        return 1
    payload = json.loads(INVENTORY.read_text(encoding="utf-8"))
    datasets = payload.get("datasets") or []
    summary = payload.get("summary") or {}

    lines: list[str] = []
    lines.append("# 训练数据集总索引（跨境电商智能选品）")
    lines.append("")
    lines.append(
        f"> 生成时间：{datetime.now(timezone.utc).astimezone().strftime('%Y-%m-%d %H:%M')}；"
        f"共 **{len(datasets)}** 个数据集，"
        f"合计约 **{summary.get('total_size_mb', 0)/1024:.2f} GB**。"
    )
    lines.append("> 机器可读清单：`data/datasets_manifest.json`；重建：`python scripts\\build_datasets_inventory.py`")
    lines.append("")
    lines.append("## 一、总览")
    lines.append("")
    lines.append("| # | 数据集 | 来源 | 模态 | 规模 | 语言 | 许可证 | 用途 | 状态 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for idx, d in enumerate(datasets, 1):
        license_txt = d.get("license", "未知")
        if "非商业" in license_txt or "NC" in license_txt:
            license_txt = f"⚠️ {license_txt}"
        lines.append(
            f"| {idx} | {d['name']} | {d['source']} | {d['modality']} "
            f"| {d['rows']} | {d['language']} | {license_txt} "
            f"| {d['usage']} | {d['status']} |"
        )
    lines.append("")

    lines.append("## 二、分组明细")
    lines.append("")
    groups: dict[str, list[dict]] = {}
    for d in datasets:
        src = d.get("source", "其他")
        if d.get("status", "").startswith("待接入"):
            group = "待接入候选（Kaggle，需凭据）"
        elif src.startswith("Hugging Face"):
            group = "Hugging Face"
        elif src.startswith("GitHub"):
            group = "GitHub"
        else:
            group = "项目流程产物"
        groups.setdefault(group, []).append(d)
    for group_name in ("Hugging Face", "GitHub", "项目流程产物", "待接入候选（Kaggle，需凭据）"):
        items = groups.get(group_name, [])
        if not items:
            continue
        lines.append(f"### {group_name}（{len(items)} 个）")
        lines.append("")
        lines.append("| 数据集 | 路径 | 规模 | 许可证 | 更新 | 链接 | 备注 |")
        lines.append("|---|---|---|---|---|---|---|")
        for d in items:
            link = f"[链接]({d['url']})" if d.get("url") else "—"
            lines.append(
                f"| **{d['name']}** | `{d['path']}` | {d['rows']} "
                f"| {d['license']} | {d['updated']} | {link} | {d.get('note', '')} |"
            )
        lines.append("")

    lines.append("## 三、用途速查")
    lines.append("")
    lines.append("| 训练目标 | 推荐数据集 |")
    lines.append("|---|---|")
    lines.append(
        "| 评论情感分析 | Amazon Polarity（360 万条）、E-Commerce Reviews Sentiment（印尼语） |"
    )
    lines.append(
        "| 产品分类/品类映射 | E-Commerce Product Classification（33 类）、AMAZON-Products-2023、HS Code |"
    )
    lines.append(
        "| 价格/销量代理 | Amazon Products Sample、eBay Sample、Octaprice、AMAZON-Products-2023、M5 |"
    )
    lines.append(
        "| 销量时序预测 | M5 Forecasting（3 万商品×1941 天）、演示市场数据（132×15 合成时序） |"
    )
    lines.append(
        "| 市场信号/对照组 | Shopee、Amazon/eBay 样例、Google Trends（output 侧） |"
    )
    lines.append("")

    lines.append("## 四、许可提醒")
    lines.append("")
    lines.append(
        "- **可商用**：HS Code（公有领域）、eBay Product Listing（CC0）、amazon_polarity（Apache-2.0）、"
        "AMAZON-Products-2023（MIT）、E-Commerce Classification（CC BY-4.0）。"
    )
    lines.append(
        "- **非商业（⚠️）**：Olist（CC BY-NC-SA）、Datafiniti 评论（CC BY-NC-SA）、42K+ Amazon（CC BY-NC）"
        "——商用演示需谨慎，建议仅用于学术验证。"
    )
    lines.append(
        "- **样例/商业**：Bright Data 的 Amazon/eBay 免费样例（全量数据集为商业产品）、Octaprice（学术用途免费）。"
    )
    lines.append(
        "- **未声明**：E-Commerce Reviews Sentiment（HF 未标注许可证），使用前建议联系作者确认。"
    )
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "*本索引由 `scripts/build_datasets_inventory.py` + `scripts/build_datasets_index.py` 自动生成；"
        "新增数据集后请重跑。*"
    )
    lines.append("")

    INDEX_MD.parent.mkdir(parents=True, exist_ok=True)
    INDEX_MD.write_text("\n".join(lines), encoding="utf-8")

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": summary,
        "datasets": datasets,
    }
    INDEX_JSON.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"已写入 {INDEX_MD}")
    print(f"已写入 {INDEX_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
