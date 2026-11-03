"""每日联网数据更新：刷新到当天、联网快照、重建并同步演示产物。

用法：
    python scripts\\run_daily_update.py            # 联网 + 全量重建
    python scripts\\run_daily_update.py --offline  # 跳过真实联网
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import pandas as pd  # noqa: E402

from src.config import (  # noqa: E402
    CATEGORIES,
    CONTROL_METRICS_JSON,
    CONTROL_OUTPUT_DIR,
    CRAWLER_DEFAULT_COMBOS,
    CRAWLER_LATEST_JSON,
    DAILY_SNAPSHOT_DIR,
    DATA_STATUS_JSON,
    DB_PATH,
    DEMO_CSV,
    DEMO_DATA_JSON,
    ENG_STATUS_JSON,
    FORECAST_CSV,
    GITHUB_DATA_DIR,
    GITHUB_REAL_RESULTS_CSV,
    GITHUB_SIGNALS_JSON,
    HF_REAL_RESULTS_CSV,
    HF_SIGNALS_JSON,
    MARKET_DAILY_PUSH_URL,
    MARKETS,
    METRICS_JSON,
    OPEN_FOOD_FACTS_LATEST_JSON,
    OUTPUT_DIR,
    PLATFORM_RANKINGS_LATEST_JSON,
    POLICY_DAILY_DIR,
    POLICY_LATEST_JSON,
    PROCESSED_CSV,
    RECOMMEND_CSV,
    REAL_PROXY_STATUS_JSON,
    REAL_TRAINING_CSV,
    REAL_TRAINING_STATUS_JSON,
    SYSTEM_EVAL_JSON,
    SUPPLIER_LATEST_JSON,
    TRENDS_LATEST_JSON,
    narrative_grid,
    NARRATIVE_3X3,
)
from src.data.daily import (  # noqa: E402
    collect_daily_snapshot,
    latest_data_date,
    refresh_demo_payloads,
    write_data_status,
)
from src.data.market_daily import (  # noqa: E402
    build_market_daily_markdown,
    market_daily_status,
    maybe_push_market_daily,
    write_market_daily,
)
from src.data.platform_rankings import (  # noqa: E402
    collect_rankings,
    rankings_status,
    save_latest_rankings,
)
from src.data.policy_refresh import (  # noqa: E402
    policy_snapshot_status,
    refresh_policy_snapshot,
)
from src.data.trends import (  # noqa: E402
    collect_trends,
    save_latest_trends,
    trends_status,
)
from src.data.customs import (  # noqa: E402
    collect_customs_exports,
    customs_status,
    save_latest_customs,
)
from src.data.open_food_facts import (  # noqa: E402
    collect_open_food_facts,
    open_food_facts_status,
    save_latest_open_food_facts,
)
from src.data.supplier_sourcing import (  # noqa: E402
    collect_suppliers,
    save_latest_suppliers,
    supplier_status,
)
from src.analysis.anomaly import (  # noqa: E402
    anomalies_status,
    build_anomalies_payload,
    save_latest_anomalies,
)
from src.data.crawl_quality import build_crawl_quality, write_coverage  # noqa: E402
from src.data.real_ingest import save_real_validation  # noqa: E402
from src.pipeline import run_full_pipeline  # noqa: E402
from train_real_enhanced import run_real_enhanced_pipeline  # noqa: E402
from src.trade.report import (  # noqa: E402
    OUTPUT_DIR as TRADE_OUTPUT_DIR,
    build_trade_demo_report,
)

_RUNPACK_ROOT = PROJECT_ROOT / "发布与材料" / "完整Demo运行包"
RUNPACK = _RUNPACK_ROOT if _RUNPACK_ROOT.exists() else None
RUNPACK_STATUS_JSON = (
    RUNPACK / "output" / "data_status.json"
    if RUNPACK
    else OUTPUT_DIR / "data_status.json"
)

DASHBOARD_COPIES = [
    PROJECT_ROOT
    / "发布与材料"
    / "提交材料包_整合优化版_20260805"
    / "02_答辩与展示"
    / "dashboard.html",
]

RUNPACK_SOURCE_SYNC = [
    (PROJECT_ROOT / "AGENTS.md", "AGENTS.md"),
    (PROJECT_ROOT / "assets" / "logo.jpg", "assets/logo.jpg"),
    (PROJECT_ROOT / "README.md", "README.md"),
    (PROJECT_ROOT / ".env.example", ".env.example"),
    (PROJECT_ROOT / "src" / "config.py", "src/config.py"),
    (PROJECT_ROOT / "src" / "features" / "builder.py", "src/features/builder.py"),
    (PROJECT_ROOT / "src" / "models" / "advanced.py", "src/models/advanced.py"),
    (PROJECT_ROOT / "src" / "models" / "baseline.py", "src/models/baseline.py"),
    (
        PROJECT_ROOT / "src" / "models" / "statsforecast_baseline.py",
        "src/models/statsforecast_baseline.py",
    ),
    (PROJECT_ROOT / "src" / "models" / "real_proxy.py", "src/models/real_proxy.py"),
    (PROJECT_ROOT / "src" / "models" / "metrics.py", "src/models/metrics.py"),
    (PROJECT_ROOT / "src" / "models" / "recommend.py", "src/models/recommend.py"),
    (PROJECT_ROOT / "src" / "trade" / "cost.py", "src/trade/cost.py"),
    (PROJECT_ROOT / "src" / "trade" / "__init__.py", "src/trade/__init__.py"),
    (PROJECT_ROOT / "src" / "trade" / "decision.py", "src/trade/decision.py"),
    (PROJECT_ROOT / "src" / "trade" / "hs_code.py", "src/trade/hs_code.py"),
    (PROJECT_ROOT / "src" / "trade" / "catalog.py", "src/trade/catalog.py"),
    (PROJECT_ROOT / "src" / "trade" / "preflight.py", "src/trade/preflight.py"),
    (PROJECT_ROOT / "src" / "trade" / "osint.py", "src/trade/osint.py"),
    (PROJECT_ROOT / "src" / "trade" / "opportunity.py", "src/trade/opportunity.py"),
    (PROJECT_ROOT / "src" / "trade" / "credit.py", "src/trade/credit.py"),
    (PROJECT_ROOT / "src" / "trade" / "green.py", "src/trade/green.py"),
    (PROJECT_ROOT / "src" / "trade" / "logistics.py", "src/trade/logistics.py"),
    (PROJECT_ROOT / "src" / "trade" / "policy.py", "src/trade/policy.py"),
    (PROJECT_ROOT / "src" / "trade" / "report.py", "src/trade/report.py"),
    (PROJECT_ROOT / "requirements.txt", "requirements.txt"),
    (PROJECT_ROOT / "src" / "data" / "base.py", "src/data/base.py"),
    (PROJECT_ROOT / "src" / "data" / "http.py", "src/data/http.py"),
    (PROJECT_ROOT / "src" / "data" / "crawl_engine.py", "src/data/crawl_engine.py"),
    (PROJECT_ROOT / "src" / "data" / "policy_common.py", "src/data/policy_common.py"),
    (PROJECT_ROOT / "src" / "data" / "search.py", "src/data/search.py"),
    (PROJECT_ROOT / "src" / "data" / "collector.py", "src/data/collector.py"),
    (PROJECT_ROOT / "src" / "data" / "cleaner.py", "src/data/cleaner.py"),
    (PROJECT_ROOT / "src" / "data" / "database.py", "src/data/database.py"),
    (PROJECT_ROOT / "src" / "data" / "__init__.py", "src/data/__init__.py"),
    (PROJECT_ROOT / "src" / "data" / "daily.py", "src/data/daily.py"),
    (PROJECT_ROOT / "src" / "data" / "crawler_signals.py", "src/data/crawler_signals.py"),
    (PROJECT_ROOT / "src" / "data" / "trends.py", "src/data/trends.py"),
    (PROJECT_ROOT / "src" / "data" / "platform_rankings.py", "src/data/platform_rankings.py"),
    (PROJECT_ROOT / "src" / "data" / "customs.py", "src/data/customs.py"),
    (
        PROJECT_ROOT / "src" / "data" / "open_food_facts.py",
        "src/data/open_food_facts.py",
    ),
    (
        PROJECT_ROOT / "src" / "data" / "supplier_sourcing.py",
        "src/data/supplier_sourcing.py",
    ),
    (PROJECT_ROOT / "src" / "data" / "market_daily.py", "src/data/market_daily.py"),
    (PROJECT_ROOT / "src" / "data" / "legal_crawler.py", "src/data/legal_crawler.py"),
    (PROJECT_ROOT / "src" / "data" / "policy_refresh.py", "src/data/policy_refresh.py"),
    (PROJECT_ROOT / "src" / "data" / "policy_sources.py", "src/data/policy_sources.py"),
    (PROJECT_ROOT / "src" / "data" / "synthetic.py", "src/data/synthetic.py"),
    (PROJECT_ROOT / "src" / "data" / "github_datasets.py", "src/data/github_datasets.py"),
    (PROJECT_ROOT / "src" / "data" / "hf_datasets.py", "src/data/hf_datasets.py"),
    (PROJECT_ROOT / "src" / "data" / "crawl_quality.py", "src/data/crawl_quality.py"),
    (PROJECT_ROOT / "src" / "data" / "real_ingest.py", "src/data/real_ingest.py"),
    (PROJECT_ROOT / "src" / "data" / "real_features.py", "src/data/real_features.py"),
    (PROJECT_ROOT / "scripts" / "fetch_github_datasets.py", "scripts/fetch_github_datasets.py"),
    (PROJECT_ROOT / "scripts" / "build_hf_real.py", "scripts/build_hf_real.py"),
    (
        PROJECT_ROOT / "scripts" / "build_datasets_inventory.py",
        "scripts/build_datasets_inventory.py",
    ),
    (PROJECT_ROOT / "scripts" / "build_datasets_index.py", "scripts/build_datasets_index.py"),
    (PROJECT_ROOT / "src" / "pipeline.py", "src/pipeline.py"),
    (PROJECT_ROOT / "src" / "api" / "app.py", "src/api/app.py"),
    (PROJECT_ROOT / "src" / "api" / "brain_bridge.py", "src/api/brain_bridge.py"),
    (PROJECT_ROOT / "src" / "four_brain" / "__init__.py", "src/four_brain/__init__.py"),
    (PROJECT_ROOT / "src" / "four_brain" / "ai_agent.py", "src/four_brain/ai_agent.py"),
    (PROJECT_ROOT / "src" / "four_brain" / "ai_provider.py", "src/four_brain/ai_provider.py"),
    (PROJECT_ROOT / "src" / "four_brain" / "data_tools.py", "src/four_brain/data_tools.py"),
    (PROJECT_ROOT / "src" / "four_brain" / "engine.py", "src/four_brain/engine.py"),
    (PROJECT_ROOT / "src" / "four_brain" / "worker.py", "src/four_brain/worker.py"),
    (PROJECT_ROOT / "src" / "checks.py", "src/checks.py"),
    (PROJECT_ROOT / "pytest.ini", "pytest.ini"),
    (
        PROJECT_ROOT / ".github" / "workflows" / "ci.yml",
        ".github/workflows/ci.yml",
    ),
    (PROJECT_ROOT / "tests" / "test_api.py", "tests/test_api.py"),
    (PROJECT_ROOT / "tests" / "test_search_api.py", "tests/test_search_api.py"),
    (PROJECT_ROOT / "tests" / "test_crawler_search.py", "tests/test_crawler_search.py"),
    (PROJECT_ROOT / "tests" / "test_ai_speed.py", "tests/test_ai_speed.py"),
    (
        PROJECT_ROOT / "tests" / "test_four_brain_isolation.py",
        "tests/test_four_brain_isolation.py",
    ),
    (
        PROJECT_ROOT / "tests" / "test_four_brain_role_prompts.py",
        "tests/test_four_brain_role_prompts.py",
    ),
    (PROJECT_ROOT / "docs" / "技术文档.md", "docs/技术文档.md"),
    (PROJECT_ROOT / "src" / "api" / "ai_config.py", "src/api/ai_config.py"),
    (PROJECT_ROOT / "src" / "api" / "control_run.py", "src/api/control_run.py"),
    (PROJECT_ROOT / "src" / "api" / "services.py", "src/api/services.py"),
    (PROJECT_ROOT / "src" / "control" / "benchmark.py", "src/control/benchmark.py"),
    (PROJECT_ROOT / "src" / "api" / "README.md", "src/api/README.md"),
    (PROJECT_ROOT / "src" / "app" / "dashboard.py", "src/app/dashboard.py"),
    (PROJECT_ROOT / "src" / "analysis" / "report.py", "src/analysis/report.py"),
    (PROJECT_ROOT / "src" / "analysis" / "evidence.py", "src/analysis/evidence.py"),
    (PROJECT_ROOT / "src" / "analysis" / "eda.py", "src/analysis/eda.py"),
    (PROJECT_ROOT / "src" / "analysis" / "stats.py", "src/analysis/stats.py"),
    (PROJECT_ROOT / "src" / "analysis" / "anomaly.py", "src/analysis/anomaly.py"),
    (SCRIPTS_DIR / "build_market_daily.py", "scripts/build_market_daily.py"),
    (SCRIPTS_DIR / "backfill_control_real.py", "scripts/backfill_control_real.py"),
    (SCRIPTS_DIR / "train_real_enhanced.py", "scripts/train_real_enhanced.py"),
    (SCRIPTS_DIR / "build_html_dashboard.py", "scripts/build_html_dashboard.py"),
    (SCRIPTS_DIR / "build_trade_catalog.py", "scripts/build_trade_catalog.py"),
    (SCRIPTS_DIR / "build_eng_status.py", "scripts/build_eng_status.py"),
    (
        SCRIPTS_DIR / "run_statsforecast_baseline.py",
        "scripts/run_statsforecast_baseline.py",
    ),
    (SCRIPTS_DIR / "run_mcp_server.py", "scripts/run_mcp_server.py"),
    (SCRIPTS_DIR / "run_api.py", "scripts/run_api.py"),
    (SCRIPTS_DIR / "__init__.py", "scripts/__init__.py"),
    (PROJECT_ROOT / "src" / "api" / "mcp_bridge.py", "src/api/mcp_bridge.py"),
    (PROJECT_ROOT / "src" / "api" / "jobs.py", "src/api/jobs.py"),
    (PROJECT_ROOT / "src" / "api" / "middleware.py", "src/api/middleware.py"),
    (PROJECT_ROOT / "src" / "api" / "store.py", "src/api/store.py"),
    (SCRIPTS_DIR / "run_daily_update.py", "scripts/run_daily_update.py"),
    (SCRIPTS_DIR / "run_policy_watch.py", "scripts/run_policy_watch.py"),
    (
        SCRIPTS_DIR / "install_policy_watch_task.ps1",
        "scripts/install_policy_watch_task.ps1",
    ),
    (SCRIPTS_DIR / "complete_demo_refresh.ps1", "scripts/complete_demo_refresh.ps1"),
    (PROJECT_ROOT / "start_complete_demo.ps1", "start_complete_demo.ps1"),
    (PROJECT_ROOT / "stop_complete_demo.ps1", "stop_complete_demo.ps1"),
    (SCRIPTS_DIR / "control_group.py", "scripts/control_group.py"),
    (SCRIPTS_DIR / "run_legal_crawler.py", "scripts/run_legal_crawler.py"),
    (SCRIPTS_DIR / "test_online.py", "scripts/test_online.py"),
    (SCRIPTS_DIR / "test_policy_sources.py", "scripts/test_policy_sources.py"),
    (SCRIPTS_DIR / "run_daily_update.bat", "scripts/run_daily_update.bat"),
    (
        SCRIPTS_DIR / "install_daily_update_task.ps1",
        "scripts/install_daily_update_task.ps1",
    ),
    (PROJECT_ROOT / "data" / "control" / "README.md", "data/control/README.md"),
    (PROJECT_ROOT / "data" / "control" / "prompt.md", "data/control/prompt.md"),
    (PROJECT_ROOT / "docs" / "skill" / "SKILL.md", "docs/skill/SKILL.md"),
    (PROJECT_ROOT / "docs" / "mcp" / "README.md", "docs/mcp/README.md"),
    (PROJECT_ROOT / "third_party" / "PROVENANCE.md", "third_party/PROVENANCE.md"),
    (
        PROJECT_ROOT / "docs" / "开源爬虫项目调研与接入方案.md",
        "docs/开源爬虫项目调研与接入方案.md",
    ),
    (
        PROJECT_ROOT
        / "third_party"
        / "scrape-do"
        / "amazon-scraper"
        / "LICENSE",
        "third_party/scrape-do/amazon-scraper/LICENSE",
    ),
    (
        PROJECT_ROOT / "third_party" / "hooper-lee" / "crosspulse" / "LICENSE",
        "third_party/hooper-lee/crosspulse/LICENSE",
    ),
    (
        PROJECT_ROOT / "third_party" / "kangise" / "ecommerce-ai-skills" / "LICENSE",
        "third_party/kangise/ecommerce-ai-skills/LICENSE",
    ),
    (
        PROJECT_ROOT / "third_party" / "cosjef" / "keepa_MCP" / "LICENSE",
        "third_party/cosjef/keepa_MCP/LICENSE",
    ),
    (
        PROJECT_ROOT / "third_party" / "superjack2050" / "1688-cli" / "LICENSE",
        "third_party/superjack2050/1688-cli/LICENSE",
    ),
    (
        PROJECT_ROOT / "third_party" / "zach22-1999" / "amazon-skills" / "LICENSE",
        "third_party/zach22-1999/amazon-skills/LICENSE",
    ),
    (
        PROJECT_ROOT / "third_party" / "nexscope-ai" / "eCommerce-Skills" / "LICENSE",
        "third_party/nexscope-ai/eCommerce-Skills/LICENSE",
    ),
]

RUNPACK_ARTIFACT_SYNC = [
    (DEMO_CSV, "data/demo/demo_market_data.csv"),
    (PROCESSED_CSV, "data/processed/clean_data.csv"),
    (PROJECT_ROOT / "data" / "processed" / "clean_data_real.csv", "data/processed/clean_data_real.csv"),
    (PROJECT_ROOT / "data" / "processed" / "real_feature_bank.csv", "data/processed/real_feature_bank.csv"),
    (DB_PATH, "data/processed/market_data.db"),
    (FORECAST_CSV, "models/forecast.csv"),
    (RECOMMEND_CSV, "models/recommendations.csv"),
    (PROJECT_ROOT / "data" / "trade_catalog.json", "data/trade_catalog.json"),
    (METRICS_JSON, "models/metrics.json"),
    (ENG_STATUS_JSON, "output/eng_status.json"),
    (SYSTEM_EVAL_JSON, "output/control/system_eval.json"),
    (CONTROL_METRICS_JSON, "output/control/control_metrics.json"),
    (CONTROL_OUTPUT_DIR / "score_summary.md", "output/control/score_summary.md"),
    (GITHUB_SIGNALS_JSON, "output/control/github_signals.json"),
    (GITHUB_REAL_RESULTS_CSV, "output/control/github_real_results.csv"),
    (HF_SIGNALS_JSON, "output/control/hf_signals.json"),
    (HF_REAL_RESULTS_CSV, "output/control/hf_real_results.csv"),
    (PROJECT_ROOT / "data" / "control" / "train_data.csv", "data/control/train_data.csv"),
    (PROJECT_ROOT / "data" / "control" / "holdout_data.csv", "data/control/holdout_data.csv"),
    (CRAWLER_LATEST_JSON, "output/crawler/latest.json"),
    (POLICY_LATEST_JSON, "output/policy/latest.json"),
    (TRENDS_LATEST_JSON, "output/trends/latest.json"),
    (PLATFORM_RANKINGS_LATEST_JSON, "output/platform_rankings/latest.json"),
    (PROJECT_ROOT / "output" / "customs" / "latest.json", "output/customs/latest.json"),
    (
        PROJECT_ROOT / "output" / "open_food_facts" / "latest.json",
        "output/open_food_facts/latest.json",
    ),
    (PROJECT_ROOT / "output" / "anomalies" / "latest.json", "output/anomalies/latest.json"),
    (SUPPLIER_LATEST_JSON, "output/suppliers/latest.json"),
    (PROJECT_ROOT / "models" / "real_demand_proxy.joblib", "models/real_demand_proxy.joblib"),
    (PROJECT_ROOT / "models" / "real_demand_proxy_meta.json", "models/real_demand_proxy_meta.json"),
    (REAL_TRAINING_STATUS_JSON, "output/real_training/status.json"),
    (REAL_PROXY_STATUS_JSON, "output/real_training/proxy_status.json"),
    (
        PROJECT_ROOT / "data" / "demo" / "pet_feeder_demo_result.json",
        "data/demo/pet_feeder_demo_result.json",
    ),
    (
        PROJECT_ROOT / "output" / "dashboard.html",
        "output/dashboard.html",
    ),
    (
        PROJECT_ROOT / "output" / "dashboard-offline.html",
        "output/dashboard-offline.html",
    ),
    (
        PROJECT_ROOT / "output" / "dashboard-data.json",
        "output/dashboard-data.json",
    ),
    (
        PROJECT_ROOT / "output" / "app-offline.html",
        "output/app-offline.html",
    ),
    (
        TRADE_OUTPUT_DIR / "trade_demo_metrics.json",
        "output/trade/trade_demo_metrics.json",
    ),
]


def _daily_queries() -> list[str]:
    return [
        f"{CATEGORIES[category]} {MARKETS[market]} 跨境电商 最新趋势 每日数据"
        for category in CATEGORIES
        for market in MARKETS
    ]


RUNPACK_DIR_SYNC = [
    (GITHUB_DATA_DIR, "data/external/github"),
    (OUTPUT_DIR / "app", "output/app"),
]


def _offline_search(query: str, max_results: int = 3, provider: str = "mock") -> dict:
    """离线模式占位：不发起真实网络请求，结果明确标注模拟。"""
    return {
        "provider": provider,
        "fallback_used": True,
        "results": [
            {
                "title": f"模拟搜索结果：{query}",
                "snippet": "离线每日更新：未发起真实联网检索，结果仅用于演示。",
                "link": "",
            }
        ][: max(1, max_results)],
    }


def _copy(path: Path, target: Path, create_parent: bool = False) -> None:
    if not path.exists():
        print(f"      跳过（源文件不存在）：{path}")
        return
    if not target.parent.exists():
        if create_parent:
            target.parent.mkdir(parents=True, exist_ok=True)
        else:
            print(f"      跳过（目录不存在）：{target}")
            return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)


def _emit(progress: Callable[..., None] | None, stage: str, message: str) -> None:
    if progress is not None:
        progress(stage, message)


def _build_react_frontend() -> None:
    """Rebuild the React frontend after the daily data refresh."""
    print("      重建 React 前端（在线 + 离线单文件）...")
    cmd = [
        "pnpm.cmd",
        "--dir",
        str(PROJECT_ROOT / "frontend"),
        "build",
    ]
    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=900,
        )
        print("      React 前端重建完成")
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"      跳过（React 前端重建失败）：{exc}")


def main(
    argv: list[str] | None = None,
    progress: Callable[..., None] | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="每日联网数据更新")
    parser.add_argument(
        "--date",
        help="数据截止日（YYYY-MM-DD），默认今天",
    )
    parser.add_argument(
        "--provider",
        help="搜索服务，默认 crawler（爬虫优先，无需 Key）",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="跳过真实联网检索，仅写模拟快照",
    )
    parser.add_argument(
        "--skip-rebuild",
        action="store_true",
        help="只更新数据与快照，不重建 HTML 演示产物",
    )
    parser.add_argument(
        "--crawler-combos",
        type=int,
        default=CRAWLER_DEFAULT_COMBOS,
        help=f"number of top recommendation combos to crawl (1-{len(CATEGORIES)})",
    )
    parser.add_argument(
        "--skip-pipeline",
        action="store_true",
        help="跳过数据重训，仅刷新快照与重建（要求已有 clean_data/forecast/recommendations）",
    )
    parser.add_argument(
        "--skip-real-features",
        action="store_true",
        help="训练时跳过真实特征增强，仅使用原始清洗数据",
    )
    parser.add_argument(
        "--skip-proxy",
        action="store_true",
        help="跳过真实销量代理模型训练",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="每日联网检索与爬虫信号的并发线程数（1 为串行）",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="即使当日快照已存在也重新联网检索",
    )
    args = parser.parse_args(argv)

    as_of = latest_data_date(args.date or pd.Timestamp.today().normalize())
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")
    provider = str(
        args.provider or os.environ.get("SEARCH_PROVIDER") or "crawler"
    ).strip().lower()
    snapshot_date = pd.Timestamp(args.date or pd.Timestamp.today().normalize()).date()

    print(f"[每日更新] 数据截止：{as_of.date().isoformat()}，生成时间：{generated_at}")
    _emit(progress, "0/6", "每日更新开始")

    _emit(progress, "1/6", "处理数据与模型")
    if args.skip_pipeline:
        print("[1/6] 跳过数据重训，读取现有产物 ...")
        if not (PROCESSED_CSV.exists() and FORECAST_CSV.exists() and RECOMMEND_CSV.exists()):
            print("错误：--skip-pipeline 需要已存在的 processed/forecast/recommendations 产物")
            return 2
        training_csv = (
            REAL_TRAINING_CSV
            if not args.skip_real_features and REAL_TRAINING_CSV.exists()
            else PROCESSED_CSV
        )
        clean_df = pd.read_csv(training_csv, encoding="utf-8-sig")
        clean_df["date"] = pd.to_datetime(clean_df["date"])
    else:
        print("[1/6] 刷新市场数据并重训模型 ...")
        result = run_real_enhanced_pipeline(
            force_regenerate=True,
            end_date=as_of,
            skip_real_features=args.skip_real_features,
            skip_proxy=args.skip_proxy,
        )
        clean_df = result["data"]
    print(
        f"      数据 {len(clean_df)} 行，最新日期 {clean_df['date'].max().date()}，"
        f"预测 {len(pd.read_csv(FORECAST_CSV, encoding='utf-8-sig')) if args.skip_pipeline else len(result['forecast'])} 行"
    )
    import build_trade_catalog

    build_trade_catalog.main()

    print("[2/6] 每日政策快照（国外 + 国内 + 全球）...")
    _emit(progress, "2/6", "刷新政策快照")
    if args.offline:
        policy_search = None
    else:
        from src.api import brain_bridge

        policy_search = brain_bridge.search
    policy_payload = refresh_policy_snapshot(
        policy_search,
        offline=args.offline,
        provider=provider,
        policy_date=snapshot_date,
    )
    policy_status = policy_snapshot_status(policy_payload)
    print(
        f"      政策事件 {policy_status['events']} 条，"
        f"国外 {policy_status['foreign']} / 国内 {policy_status['domestic']} / "
        f"全球 {policy_status['global']}，回退 {policy_status['fallback_used']}"
    )

    print("[3/6] 真实数据源采集（Google Trends + 平台榜单 + 海关出口）...")
    _emit(progress, "3/6", "采集真实数据源")
    trends = collect_trends(offline=args.offline)
    save_latest_trends(trends)
    print(
        f"      trends provider={trends['provider']}, "
        f"fallback={trends['fallback_used']}, series={trends['series_count']}"
    )
    rankings = collect_rankings(offline=args.offline)
    save_latest_rankings(rankings)
    print(
        f"      rankings rows={rankings['source_count']}, "
        f"fallback={rankings['fallback_used']}"
    )
    customs = collect_customs_exports(offline=args.offline)
    save_latest_customs(customs)
    print(
        f"      customs provider={customs['provider']}, "
        f"period={customs['period']}, rows={customs['source_count']}, "
        f"fallback={customs['fallback_used']}"
    )
    open_food_facts = collect_open_food_facts(offline=args.offline)
    save_latest_open_food_facts(open_food_facts)
    print(
        f"      open_food_facts provider={open_food_facts['provider']}, "
        f"rows={open_food_facts['source_count']}, "
        f"fallback={open_food_facts['fallback_used']}"
    )
    anomalies = build_anomalies_payload(clean_df)
    save_latest_anomalies(anomalies)
    print(
        f"      anomalies rows={anomalies['source_count']}, "
        f"method={anomalies['method']}"
    )
    suppliers = collect_suppliers(offline=args.offline)
    save_latest_suppliers(suppliers)
    print(
        f"      suppliers provider={suppliers['provider']}, "
        f"rows={suppliers['source_count']}, fallback={suppliers['fallback_used']}"
    )

    print("[4/6] 重建贸易决策报告 ...")
    _emit(progress, "4/6", "重建贸易决策报告")
    trade_report = build_trade_demo_report(clean_df)
    print(
        f"      组合 {trade_report['summary']['combos']}，"
        f"平均利润率 {trade_report['summary']['avg_margin_pct']}%"
    )

    print(f"[5/6] 每日联网快照（provider={provider}）...")
    _emit(progress, "5/6", "每日联网快照")
    print("      crawler signals (top recommendation combos) ...")
    from src.data.crawler_signals import build_daily_combos, build_snapshot

    crawler_recs = pd.read_csv(RECOMMEND_CSV, encoding="utf-8-sig")
    crawler = build_snapshot(
        build_daily_combos(crawler_recs, args.crawler_combos),
        offline=args.offline,
        out_path=CRAWLER_LATEST_JSON,
        workers=args.workers,
    )
    print(
        f"      crawler {len(crawler['combos'])} combos, "
        f"sources {crawler['sources_count']}, fallback {crawler['fallback_used']}"
    )

    snapshot_path = DAILY_SNAPSHOT_DIR / f"{snapshot_date.isoformat()}.json"
    if snapshot_path.exists() and not args.force:
        print(f"      复用已有当日快照 {snapshot_path.name}（--force 可强制重抓）")
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    elif args.offline:
        snapshot = collect_daily_snapshot(
            _offline_search,
            _daily_queries(),
            provider,
            DAILY_SNAPSHOT_DIR,
            snapshot_date,
            workers=args.workers,
        )
    else:
        from src.api import brain_bridge

        snapshot = collect_daily_snapshot(
            brain_bridge.search,
            _daily_queries(),
            provider,
            DAILY_SNAPSHOT_DIR,
            snapshot_date,
            workers=args.workers,
        )
    print(
        f"      快照 {snapshot_path.name}，来源 {snapshot['sources_count']} 条，"
        f"回退 {snapshot['fallback_used']}"
    )

    daily_markdown = build_market_daily_markdown(
        snapshot_date,
        crawler=crawler,
        policy=policy_payload,
        trends=trends,
        rankings=rankings,
        customs=customs,
        anomalies=anomalies,
        suppliers=suppliers,
    )
    write_market_daily(daily_markdown, snapshot_date)
    if MARKET_DAILY_PUSH_URL:
        pushed = maybe_push_market_daily(daily_markdown)
        print(f"      市场日报推送：{'成功' if pushed else '失败'}")
    else:
        print("      市场日报未配置 webhook，仅写入本地文件")

    print("[6/6] 刷新演示数据与状态 ...")
    _emit(progress, "6/6", "刷新演示数据与状态")
    history = pd.read_csv(PROCESSED_CSV, encoding="utf-8-sig")
    forecast = pd.read_csv(FORECAST_CSV, encoding="utf-8-sig")
    recommendations = pd.read_csv(RECOMMEND_CSV, encoding="utf-8-sig")
    metrics = json.loads(METRICS_JSON.read_text(encoding="utf-8"))
    refresh_demo_payloads(
        history,
        forecast,
        recommendations,
        metrics,
        trade_report,
        as_of.date().isoformat(),
        DEMO_DATA_JSON,
        crawler=crawler,
    )
    real_training_status = (
        json.loads(REAL_TRAINING_STATUS_JSON.read_text(encoding="utf-8"))
        if REAL_TRAINING_STATUS_JSON.exists()
        else {"enabled": False}
    )
    proxy_status = (
        json.loads(REAL_PROXY_STATUS_JSON.read_text(encoding="utf-8"))
        if REAL_PROXY_STATUS_JSON.exists()
        else {"enabled": False}
    )
    status = write_data_status(
        OUTPUT_DIR,
        data_as_of=as_of.date().isoformat(),
        generated_at=generated_at,
        provider=provider,
        fallback_used=snapshot["fallback_used"],
        snapshot_path="output/daily_snapshots/" + snapshot_path.name,
        sources_count=snapshot["sources_count"],
        crawler=crawler,
        policy=policy_status,
        trends=trends_status(trends),
        platform_rankings=rankings_status(rankings),
        market_daily=market_daily_status(snapshot_date),
        customs=customs_status(customs),
        open_food_facts=open_food_facts_status(open_food_facts),
        anomalies=anomalies_status(anomalies),
        suppliers=supplier_status(suppliers),
        real_training=real_training_status,
        real_proxy=proxy_status,
        updated_files=[
            "data/processed/clean_data.csv",
            "data/processed/clean_data_real.csv",
            "data/processed/real_feature_bank.csv",
            "models/forecast.csv",
            "models/recommendations.csv",
            "models/metrics.json",
            "models/real_demand_proxy.joblib",
            "models/real_demand_proxy_meta.json",
            "output/trade/trade_demo_metrics.json",
            "output/policy/latest.json",
            "output/daily_snapshots/" + snapshot_path.name,
            "output/crawler/latest.json",
            "output/trends/latest.json",
            "output/platform_rankings/latest.json",
            "output/customs/latest.json",
            "output/open_food_facts/latest.json",
            "output/anomalies/latest.json",
            "output/suppliers/latest.json",
            "output/market_daily/" + snapshot_date.isoformat() + ".md",
            "output/dashboard.html",
            "output/crawl_quality/coverage.json",
            "output/real/status.json",
            "output/real/validation.json",
            "output/real_training/status.json",
            "output/real_training/proxy_status.json",
        ],
    )
    print(f"      状态文件 {DATA_STATUS_JSON.name}：{status['as_of_label']}")
    quality = build_crawl_quality(status)
    status["crawl_quality"] = quality
    status["decision_data_ready"] = quality["decision_data_ready"]
    write_coverage(quality)
    real_status = save_real_validation()
    status["real_data"] = real_status
    # B-3：3×3 收敛 9 格标注（real/planned）+ 验收阈值，占比权威口径见
    # reports/数据覆盖率盘点_20260821.md（scripts/build_coverage_report.py 幂等产出）
    grid = narrative_grid()
    status["narrative_3x3"] = {
        "label": NARRATIVE_3X3["label"],
        "categories": list(NARRATIVE_3X3["categories"]),
        "markets_real": list(NARRATIVE_3X3["markets_real"]),
        "markets_planned": list(NARRATIVE_3X3["markets_planned"]),
        "real_ratio_threshold": NARRATIVE_3X3["real_ratio_threshold"],
        "grid": grid,
        "real_cells": sum(1 for cell in grid if cell["status"] == "real"),
        "note": NARRATIVE_3X3["note"],
        "coverage_report": "reports/数据覆盖率盘点_20260821.md",
    }
    DATA_STATUS_JSON.write_text(
        json.dumps(status, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        f"      爬取质量：decision_data_ready={status['decision_data_ready']}，"
        f"真实证据组合={real_status['evidence_available_combos']}"
    )

    _emit(progress, "7/7", "重建看板并同步分发副本")
    if args.skip_rebuild:
        print("[7/7] 已跳过 HTML 重建（--skip-rebuild）")
    else:
        print("[7/7] 重建看板并同步分发副本 ...")
        import build_html_dashboard

        build_html_dashboard.build()
        output_dashboard = PROJECT_ROOT / "output" / "dashboard-offline.html"
        for target in DASHBOARD_COPIES:
            _copy(output_dashboard, target)

        _build_react_frontend()

        print("      重建 06B 系统评测指标 ...")
        try:
            import build_system_eval

            build_system_eval.main()
        except (Exception, SystemExit) as exc:  # noqa: BLE001 - 评测失败不应阻断分发同步
            print(f"      跳过（评测失败）：{exc}")

        print("      重建 AI 对照组指标 ...")
        try:
            import control_group

            control_group.prepare_command()
            control_group.score_all()
        except (Exception, SystemExit) as exc:  # noqa: BLE001 - 对照组重建失败不应阻断分发同步
            print(f"      跳过（对照组重建失败）：{exc}")

        _copy(DATA_STATUS_JSON, RUNPACK_STATUS_JSON)
        if RUNPACK is not None:
            _copy(
                snapshot_path,
                RUNPACK / "output" / "daily_snapshots" / snapshot_path.name,
                create_parent=True,
            )
            policy_daily = POLICY_DAILY_DIR / f"{snapshot_date.isoformat()}.json"
            _copy(
                policy_daily,
                RUNPACK / "output" / "policy" / "daily" / policy_daily.name,
                create_parent=True,
            )
            for source, relative in RUNPACK_SOURCE_SYNC:
                _copy(source, RUNPACK / relative, create_parent=True)
            for source, relative in RUNPACK_ARTIFACT_SYNC:
                _copy(source, RUNPACK / relative, create_parent=True)
            for source, relative in RUNPACK_DIR_SYNC:
                shutil.copytree(source, RUNPACK / relative, dirs_exist_ok=True)
        for target in DASHBOARD_COPIES:
            print(f"      同步 {target.relative_to(PROJECT_ROOT)}")

    print("[完成] 每日联网数据更新结束")
    _emit(progress, "done", "每日更新完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
