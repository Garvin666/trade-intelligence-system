"""顶级 AI 对照组 CLI：prepare / run / score。"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.control.benchmark import (  # noqa: E402
    CONTROL_MODES,
    CONTROL_TIMEOUT_SECONDS,
    MODEL_REGISTRY,
    load_env_file,
    prepare_command,
    run_global_benchmark,
    run_model,
    save_web_response,
    score_all,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="顶级 AI 对照组评测")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("prepare", help="切分训练集与隐藏测试集")

    run_parser = sub.add_parser("run", help="运行 AI 对照（推荐 --global 使用全局配置）")
    run_parser.add_argument("--model", choices=list(MODEL_REGISTRY), help="旧版兼容：指定模型")
    run_parser.add_argument("--model-id", help="覆盖模型 ID（--global 时优先于 OPENAI_MODEL）")
    run_parser.add_argument("--run", type=int, choices=[1, 2], help="指定运行序号")
    run_parser.add_argument("--all", action="store_true", help="旧版兼容：运行所有有 Key 的模型")
    run_parser.add_argument("--temperature", type=float, default=0.2)
    run_parser.add_argument(
        "--global",
        dest="global_run",
        action="store_true",
        help="使用 OpenAI 兼容全局配置运行（新版推荐）",
    )
    run_parser.add_argument("--api-key", help="OpenAI 兼容 API Key（--global 时优先于 OPENAI_API_KEY）")
    run_parser.add_argument("--base-url", help="OpenAI 兼容 Base URL（--global 时优先于 OPENAI_BASE_URL）")
    run_parser.add_argument("--runs", type=int, default=2, help="--global 运行次数（1-4）")
    run_parser.add_argument(
        "--timeout",
        type=int,
        default=CONTROL_TIMEOUT_SECONDS,
        help="--global 单次请求超时秒数",
    )
    run_parser.add_argument(
        "--mode",
        choices=list(CONTROL_MODES),
        default="lite",
    help="对照口径：lite=12 组合轻量；full=按市场分批跑完整 23760 格",
    )

    score_parser = sub.add_parser("score", help="解析并评分已保存的回复")
    score_parser.add_argument(
        "--model",
        choices=list(MODEL_REGISTRY) + ["global"],
        help="只评分指定模型（global 为页面全局 AI 对照）",
    )

    web_parser = sub.add_parser(
        "web",
        help="旧版兼容：保存 DeepSeek 网页版回复并评分（无需 API Key）",
    )
    web_parser.add_argument(
        "--run",
        type=int,
        choices=[1, 2],
        required=True,
        help="运行序号 1 或 2",
    )
    source_group = web_parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--text", help="直接粘贴的完整回复内容")
    source_group.add_argument("--file", help="保存完整回复的文件路径（原样读取）")
    web_parser.add_argument("--model-version", help="网页版页面显示的模型版本")
    web_parser.add_argument(
        "--code-execution",
        action="store_true",
        help="本次运行是否启用了网页版代码执行",
    )
    web_parser.add_argument("--note", help="可选备注")

    args = parser.parse_args()
    load_env_file()

    if args.command == "prepare":
        summary = prepare_command()
        print("对照组数据切分完成：")
        for key, value in summary.items():
            print(f"  {key}: {value}")

    elif args.command == "run":
        if args.global_run:
            api_key = (args.api_key or os.environ.get("OPENAI_API_KEY") or "").strip()
            base_url = (
                args.base_url
                or os.environ.get("OPENAI_BASE_URL")
                or "https://api.deepseek.com/v1"
            ).strip()
            model = (args.model_id or os.environ.get("OPENAI_MODEL") or "").strip()
            if not api_key or not model:
                parser.error(
                    "run --global 需要 API Key 与模型（--api-key/--model-id 或 OPENAI_API_KEY/OPENAI_MODEL）"
                )
            result = run_global_benchmark(
                api_key=api_key,
                base_url=base_url,
                model=model,
                runs=args.runs,
                temperature=args.temperature,
                timeout=args.timeout,
                mode=args.mode,
            )
            print(
                f"[完成] 全局 AI 对照 {model}（{args.mode}）："
                f"{list(result.get('models', {}))}"
            )
        else:
            if not (args.all or args.model):
                parser.error("run 需要 --global、--model 或 --all")
            targets = list(MODEL_REGISTRY) if args.all else [args.model]
            runs = [1, 2] if args.run is None else [args.run]
            for model in targets:
                for run in runs:
                    result = run_model(model, run, temperature=args.temperature, model_id=args.model_id)
                    if result["status"] == "skipped":
                        print(f"[跳过] {model} run{run}: {result['reason']}")
                    else:
                        print(f"[完成] {model} run{run} -> {result['file']}")
        print("汇总文件：output/control/score_summary.md")
        print("明细文件：output/control/control_metrics.json")

    elif args.command == "score":
        payload = score_all(models=[args.model] if args.model else None)
        print(f"评分完成：{list(payload['models'].keys())}")
        print("汇总文件：output/control/score_summary.md")
        print("明细文件：output/control/control_metrics.json")

    elif args.command == "web":
        text = Path(args.file).read_text(encoding="utf-8") if args.file else args.text
        result = save_web_response(
            run=args.run,
            text=text,
            model_version=args.model_version,
            code_execution=args.code_execution,
            note=args.note,
        )
        print(f"[完成] DeepSeek 网页版 run{result['run']} -> {result['file']}")
        print("评分完成：deepseek")
        print("汇总文件：output/control/score_summary.md")
        print("明细文件：output/control/control_metrics.json")


if __name__ == "__main__":
    main()
