"""顶级 AI 对照组：数据切分、API 调用、回复解析与评分。

设计要点：
- 与现有 TEST_WEEKS=12 同口径：每个品类/市场组合最近 12 周作为隐藏测试集。
- 标准协议为单轮提问，回复原样存档，由 score 子命令统一解析评分。
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import time
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
import requests

from src.analysis.stats import ALPHA, bh_adjust, paired_significance
from src.config import (
    CATEGORY_CATALOG,
    CATEGORIES,
    CONTROL_RETRY_LIMIT,
    DATA_DIR,
    GITHUB_PROMPT_SIGNAL_ROWS_FULL,
    GITHUB_PROMPT_SIGNAL_ROWS_LITE,
    GITHUB_SIGNALS_JSON,
    HF_PROMPT_SIGNAL_ROWS_FULL,
    HF_PROMPT_SIGNAL_ROWS_LITE,
    HF_SIGNALS_JSON,
    MARKETS,
    METRICS_JSON,
    PROCESSED_CSV,
    PROJECT_ROOT,
    REAL_TRAINING_CSV,
    RECOMMEND_CSV,
    TEST_WEEKS,
)
from src.data.github_datasets import load_github_signals, signal_summary
from src.data.hf_datasets import load_hf_signals as _load_hf_signals
from src.data.hf_datasets import signal_summary as hf_signal_summary

COMBO_COUNT = len(CATEGORIES) * len(MARKETS)

# 目录与文件
CONTROL_DIR = DATA_DIR / "control"
RESPONSES_DIR = CONTROL_DIR / "responses"
TRAIN_CSV = CONTROL_DIR / "train_data.csv"
HOLDOUT_CSV = CONTROL_DIR / "holdout_data.csv"
PROMPT_MD = CONTROL_DIR / "prompt.md"
OUTPUT_DIR = PROJECT_ROOT / "output" / "control"

# 模型注册表：环境变量可覆盖模型 ID，默认值仅为兜底。
MODEL_REGISTRY = {
    "deepseek": {
        "label": "DeepSeek",
        "env_key": "DEEPSEEK_API_KEY",
        "env_model": "DEEPSEEK_MODEL",
        "default_model": "deepseek-chat",
    },
}

DEEPSEEK_WEB_URL = "https://chat.deepseek.com"

# 轻量对照默认组合：覆盖 12 个食品大类，单次请求即可完成。
CONTROL_LITE_COMBOS: list[tuple[str, str]] = [
    ("cn_latiao", "us"),
    ("cn_changsha_mifen", "sea"),
    ("cn_beef_jerky", "eu"),
    ("cn_shrimp_paste", "jp"),
    ("cn_dried_shitake", "ca"),
    ("cn_longjing", "au"),
    ("intl_matcha", "uk"),
    ("cn_laoganma", "kr"),
    ("cn_mooncake", "de"),
    ("cn_xinjiang_dates", "fr"),
    ("intl_almonds", "vn"),
    ("cn_self_heating_hotpot", "mx"),
]


# 食品品类别名表：由 132 食品 SKU 目录派生（code / 中文名 / 英文小写 / 搜索关键词），
# 剔除全部消费类目硬编码；用于把 AI 回复文本归一化回食品品类编码。
CONTROL_MODES = ("lite", "full")
CONTROL_TIMEOUT_SECONDS = 600
CONTROL_NETWORK_RETRIES = 2
_CONTROL_RETRY_BACKOFF_SECONDS = (4, 8)
_RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}

CATEGORY_ALIASES: dict[str, set[str]] = {
    code: {code, str(meta["name_cn"]), str(meta["name_en"]).lower(), str(meta["keyword"])}
    for code, meta in CATEGORY_CATALOG.items()
}


MARKET_ALIASES = {
    "us": {"us", "美国"},
    "eu": {"eu", "欧洲", "欧盟"},
    "sea": {"sea", "东南亚"},
    "jp": {"jp", "日本"},
    "ca": {"ca", "加拿大"},
    "au": {"au", "澳大利亚"},
    "uk": {"uk", "英国"},
    "kr": {"kr", "韩国"},
    "de": {"de", "德国"},
    "fr": {"fr", "法国"},
    "vn": {"vn", "越南"},
    "ru": {"ru", "俄罗斯"},
    "hu": {"hu", "匈牙利"},
    "ae": {"ae", "中东", "阿联酋"},
    "mx": {"mx", "墨西哥"},
}

# 可行动性关键词
INVENTORY_KEYWORDS = ("库存", "备货", "进货", "补货", "进多少", "采购量")
UNCERTAINTY_KEYWORDS = ("置信", "区间", "80%", "90%", "不确定性", "风险")
ASSUMPTION_KEYWORDS = ("假设", "局限", "前提", "简化")

_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_WEEK_RE = re.compile(r"(?:第\s*)?(\d{1,2})\s*(?:周|week|w)\b", re.IGNORECASE)
_WEEK_PREFIX_RE = re.compile(r"\b(?:week|w)\s*(\d{1,2})\b", re.IGNORECASE)


def load_env_file(env_path: Path | None = None) -> None:
    """从项目根目录 .env 读取 Key（不覆盖已存在的环境变量）。"""
    path = env_path or (PROJECT_ROOT / ".env")
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


from src.control.benchmark_parsing import (
    prepare_control_split,
    prepare_command,
    _normalize_category,
    _normalize_market,
    _is_float,
    _week_index,
    _tokens,
    _pairs_in_line,
    _parse_row_tokens,
    _column_role,
    _parse_csv_block,
    extract_forecast_table,
    parse_recommendations,
    _section_body,
    _has_heading,
    section_completeness,
    check_number_grounded,
    extract_numeric_claims,
    _combo_metrics,
    _top_combos,
    _actual_top5,
    _ground_claim,
    score_response,
)
def baseline_means() -> dict:
    """读取现有系统评估结果；缺失时回退到 README 中的数值。"""
    if METRICS_JSON.exists():
        payload = json.loads(METRICS_JSON.read_text(encoding="utf-8"))
        return {
            "prophet_mape": round(float(np.mean([r["mape"] for r in payload.get("baseline", [])])), 4),
            "lightgbm_mape": round(float(np.mean([r["mape"] for r in payload.get("advanced", [])])), 4),
        }
    return {"prophet_mape": 7.73, "lightgbm_mape": 3.14}


def _system_mae_by_combo() -> pd.Series:
    if not METRICS_JSON.exists():
        return pd.Series(dtype=float)
    payload = json.loads(METRICS_JSON.read_text(encoding="utf-8"))
    rows = payload.get("advanced") or []
    return pd.Series(
        {
            (str(row.get("category")), str(row.get("market"))): float(row.get("mae", 0))
            for row in rows
            if row.get("mae") is not None
        }
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _holdout_dates() -> list[str]:
    if not HOLDOUT_CSV.exists():
        raise FileNotFoundError(f"缺少 {HOLDOUT_CSV}，请先运行 prepare")
    holdout = pd.read_csv(HOLDOUT_CSV, parse_dates=["date"])
    return sorted(holdout["date"].dt.strftime("%Y-%m-%d").unique().tolist())


def _github_signal_section(combos: list[tuple[str, str]] | None) -> str:
    payload = load_github_signals(GITHUB_SIGNALS_JSON)
    if not payload.get("sources") or not payload.get("rows"):
        raise FileNotFoundError(
            "缺少 GitHub 真实信号，请先运行 scripts/backfill_control_real.py"
        )
    if combos is None or len(combos) > 12:
        max_rows = GITHUB_PROMPT_SIGNAL_ROWS_FULL
    else:
        max_rows = GITHUB_PROMPT_SIGNAL_ROWS_LITE
    return signal_summary(combos, max_rows=max_rows, payload=payload)


def _github_signal_meta() -> dict[str, str]:
    return {
        "github_signals_file": str(GITHUB_SIGNALS_JSON),
        "github_signals_sha256": (
            _sha256(GITHUB_SIGNALS_JSON) if GITHUB_SIGNALS_JSON.exists() else ""
        ),
    }


def _hf_signal_section(combos: list[tuple[str, str]] | None) -> str:
    payload = _load_hf_signals(HF_SIGNALS_JSON)
    if not payload.get("sources") or not payload.get("rows"):
        return (
            "（HF 公开数据集信号缺失，未生成；"
            "可运行 scripts/build_hf_real.py 构建）\n"
        )
    if combos is None or len(combos) > 12:
        max_rows = HF_PROMPT_SIGNAL_ROWS_FULL
    else:
        max_rows = HF_PROMPT_SIGNAL_ROWS_LITE
    return hf_signal_summary(combos, max_rows=max_rows, payload=payload)


def _hf_signal_meta() -> dict[str, str]:
    return {
        "hf_signals_file": str(HF_SIGNALS_JSON),
        "hf_signals_sha256": (
            _sha256(HF_SIGNALS_JSON) if HF_SIGNALS_JSON.exists() else ""
        ),
    }


def _user_content(combos: list[tuple[str, str]] | None = None) -> str:
    if not PROMPT_MD.exists():
        raise FileNotFoundError(f"缺少提示词文件 {PROMPT_MD}")
    if not TRAIN_CSV.exists():
        raise FileNotFoundError(f"缺少 {TRAIN_CSV}，请先运行 prepare")
    prompt = PROMPT_MD.read_text(encoding="utf-8")
    dates = _holdout_dates()
    date_text = f"{dates[0]} 至 {dates[-1]}" if dates else "未来 12 周"
    prompt = re.sub(
        r"\d{4}-\d{2}-\d{2}\s*至\s*\d{4}-\d{2}-\d{2}",
        date_text,
        prompt,
    )
    if combos is None:
        full_combos = len(CATEGORIES) * len(MARKETS)
        full_cells = full_combos * TEST_WEEKS
        prompt = re.sub(
            r"数据共 \d+ 个品类 × 市场组合（\d+ 品类 × 15 市场）",
            f"数据共 {full_combos} 个品类 × 市场组合（{len(CATEGORIES)} 品类 × 15 市场）",
            prompt,
        )
        prompt = re.sub(
            r"对全部 \d+ 个组合",
            f"对全部 {full_combos} 个组合",
            prompt,
        )
        prompt = re.sub(
            r"全部 \d+ × \d+ = \d+ 个预测值",
            f"全部 {full_combos} × {TEST_WEEKS} = {full_cells} 个预测值",
            prompt,
        )
        csv_text = TRAIN_CSV.read_text(encoding="utf-8")
        base = f"{prompt}\n\n## 数据文件内容（train_data.csv）\n\n```csv\n{csv_text}\n```\n"
        return (
            base
            + "\n"
            + _github_signal_section(None)
            + "\n"
            + _hf_signal_section(None)
        )

    cells = len(combos) * TEST_WEEKS
    prompt = re.sub(
        r"数据共 \d+ 个品类 × 市场组合（\d+ 品类 × 15 市场）",
        f"数据共 {len(combos)} 个品类 × 市场组合（{len(combos)} 品类 × 15 市场）",
        prompt,
    )
    prompt = re.sub(
        r"对全部 \d+ 个组合",
        f"对数据文件中的 {len(combos)} 个组合",
        prompt,
    )
    prompt = re.sub(
        r"全部 \d+ × \d+ = \d+ 个预测值",
        f"全部 {len(combos)} × {TEST_WEEKS} = {cells} 个预测值",
        prompt,
    )
    combo_set = set(combos)
    train = pd.read_csv(TRAIN_CSV, parse_dates=["date"])
    keys = list(zip(train["category"], train["market"]))
    mask = pd.Series([key in combo_set for key in keys], index=train.index)
    train = train[mask].sort_values(["category", "market", "date"])
    csv_text = train.to_csv(index=False)
    combo_text = "、".join(f"{cat}×{mkt}" for cat, mkt in combos)
    base = (
        f"{prompt}\n\n## 数据文件内容（train_data.csv，本批次切片）\n\n"
        f"```csv\n{csv_text}\n```\n\n"
        f"## 本批次要求\n"
        f"本批次数据文件仅包含 {len(combos)} 个组合：{combo_text}。\n"
        f"请只预测这些组合在 {date_text} 每周五的 sales_volume，"
        f"共 {len(combos)} × {TEST_WEEKS} = {cells} 行。\n"
    )
    return (
        base
        + "\n"
        + _github_signal_section(combos)
        + "\n"
        + _hf_signal_section(combos)
    )


def _call_openai(key: str, model: str, content: str, temperature: float, timeout: int) -> str:
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "temperature": temperature,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"] or ""


def _call_openai_compatible(
    key: str,
    base_url: str,
    model: str,
    content: str,
    temperature: float,
    timeout: int,
) -> str:
    """Call any OpenAI-compatible chat completions endpoint."""
    base = base_url.rstrip("/")
    url = base if base.endswith("/chat/completions") else base + "/chat/completions"
    last_error: Exception | None = None
    last_status = 0
    last_body = ""
    for attempt in range(CONTROL_NETWORK_RETRIES + 1):
        try:
            resp = requests.post(
                url,
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": content}],
                    "temperature": temperature,
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"] or ""
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_error = exc
        except requests.HTTPError as exc:
            last_error = exc
            last_status = getattr(resp, "status_code", 0)
            last_body = str(getattr(resp, "text", "") or "").strip()[:800]
            if last_status not in _RETRYABLE_HTTP_STATUS:
                raise RuntimeError(
                    f"AI 接口错误 {last_status}: {last_body or str(exc)}"
                ) from exc
        if attempt < CONTROL_NETWORK_RETRIES:
            time.sleep(_CONTROL_RETRY_BACKOFF_SECONDS[attempt])
    if last_status:
        raise RuntimeError(
            f"AI 接口错误 {last_status}: {last_body or str(last_error)}"
        ) from last_error
    raise RuntimeError(
        f"AI 接口连续失败 {CONTROL_NETWORK_RETRIES + 1} 次：{last_error}"
    ) from last_error


def _call_anthropic(key: str, model: str, content: str, temperature: float, timeout: int) -> str:
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 8192,
            "temperature": temperature,
            "messages": [{"role": "user", "content": content}],
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return "".join(
        block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
    )


def _call_gemini(key: str, model: str, content: str, temperature: float, timeout: int) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    resp = requests.post(
        url,
        params={"key": key},
        json={
            "contents": [{"parts": [{"text": content}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": 8192},
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    try:
        parts = data["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError):
        return ""
    return "".join(part.get("text", "") for part in parts)


def _call_deepseek(key: str, model: str, content: str, temperature: float, timeout: int) -> str:
    resp = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "temperature": temperature,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"] or ""


def call_model(model_key: str, api_key: str, model_id: str, content: str, temperature: float = 0.2, timeout: int = 180) -> str:
    """调用对应模型 API 并返回正文文本。"""
    if model_key == "chatgpt":
        return _call_openai(api_key, model_id, content, temperature, timeout)
    if model_key == "claude":
        return _call_anthropic(api_key, model_id, content, temperature, timeout)
    if model_key == "gemini":
        return _call_gemini(api_key, model_id, content, temperature, timeout)
    if model_key == "deepseek":
        return _call_deepseek(api_key, model_id, content, temperature, timeout)
    raise ValueError(f"未知模型: {model_key}")


def run_model(model_key: str, run: int, temperature: float = 0.2, model_id: str | None = None) -> dict:
    """执行一次 API 运行并保存回复与元数据；无 Key 时跳过。"""
    info = MODEL_REGISTRY[model_key]
    key = os.environ.get(info["env_key"])
    if not key:
        return {"status": "skipped", "model": model_key, "reason": f"缺少 {info['env_key']}"}
    used_model = model_id or os.environ.get(info["env_model"], info["default_model"])
    content = _user_content()
    text = call_model(model_key, key, used_model, content, temperature=temperature)

    out_dir = RESPONSES_DIR / model_key
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"run{run}.md"
    md_path.write_text(text, encoding="utf-8")
    meta = {
        "model": model_key,
        "label": info["label"],
        "api_model_id": used_model,
        "run": run,
        "source": "api",
        "temperature": temperature,
        "code_execution": False,
        "timestamp_utc": pd.Timestamp.utcnow().isoformat(timespec="seconds"),
        "prompt_file": str(PROMPT_MD),
        "prompt_sha256": _sha256(PROMPT_MD),
        "train_csv": str(TRAIN_CSV),
        "train_csv_sha256": _sha256(TRAIN_CSV),
        **_github_signal_meta(),
        **_hf_signal_meta(),
    }
    meta_path = out_dir / f"run{run}.meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "ok", "model": model_key, "run": run, "file": str(md_path)}


def web_setup() -> dict:
    """返回 DeepSeek 网页版对照运行所需信息（无需 API Key）。"""
    if not PROMPT_MD.exists():
        raise FileNotFoundError(f"缺少提示词文件 {PROMPT_MD}")
    if not TRAIN_CSV.exists():
        raise FileNotFoundError(f"缺少 {TRAIN_CSV}，请先运行 scripts/control_group.py prepare")
    train = pd.read_csv(TRAIN_CSV, usecols=["date"])
    runs: dict[str, dict] = {}
    for run in (1, 2):
        md_path = RESPONSES_DIR / "deepseek" / f"run{run}.md"
        meta_path = RESPONSES_DIR / "deepseek" / f"run{run}.meta.json"
        meta: dict = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                meta = {"parse_error": True}
        runs[str(run)] = {"saved": md_path.exists(), "meta": meta}
    return {
        "deepseek_url": DEEPSEEK_WEB_URL,
        "prompt_text": PROMPT_MD.read_text(encoding="utf-8"),
        "prompt_file": str(PROMPT_MD),
        "prompt_sha256": _sha256(PROMPT_MD),
        "train_csv": str(TRAIN_CSV),
        "train_csv_size": TRAIN_CSV.stat().st_size,
        "train_rows": int(len(train)),
        "train_dates": f"{train['date'].min()} ~ {train['date'].max()}",
        "runs": runs,
    }


def save_web_response(
    run: int,
    text: str,
    model_version: str | None = None,
    code_execution: bool = False,
    note: str = "",
) -> dict:
    """保存一次 DeepSeek 网页版回复并立即评分（无需 API Key）。"""
    if run not in (1, 2):
        raise ValueError("run 只能是 1 或 2")
    if not text or not str(text).strip():
        raise ValueError("回复内容不能为空")
    model_key = "deepseek"
    info = MODEL_REGISTRY[model_key]
    out_dir = RESPONSES_DIR / model_key
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"run{run}.md"
    md_path.write_text(str(text), encoding="utf-8")
    meta = {
        "model": model_key,
        "label": info["label"],
        "api_model_id": str(model_version or "").strip() or "DeepSeek Chat（网页版）",
        "run": run,
        "source": "web",
        "temperature": None,
        "code_execution": bool(code_execution),
        "timestamp_utc": pd.Timestamp.utcnow().isoformat(timespec="seconds"),
        "prompt_file": str(PROMPT_MD),
        "prompt_sha256": _sha256(PROMPT_MD),
        "train_csv": str(TRAIN_CSV),
        "train_csv_sha256": _sha256(TRAIN_CSV),
        **_github_signal_meta(),
        **_hf_signal_meta(),
        "note": str(note or "").strip(),
    }
    (out_dir / f"run{run}.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    metrics = score_all([model_key])
    return {
        "status": "ok",
        "model": model_key,
        "run": run,
        "file": str(md_path),
        "meta": meta,
        "metrics": metrics,
    }


def _control_scope(mode: str) -> dict:
    if mode == "lite":
        return {
            "mode": "lite",
            "combos": [list(c) for c in CONTROL_LITE_COMBOS],
            "total_cells": len(CONTROL_LITE_COMBOS) * TEST_WEEKS,
        }
    return {
        "mode": "full",
        "combos": "all",
        "total_cells": COMBO_COUNT * TEST_WEEKS,
    }


def _control_batches(mode: str) -> list[list[tuple[str, str]]]:
    if mode == "lite":
        return [list(CONTROL_LITE_COMBOS)]
    return [[(cat, mkt) for cat in CATEGORIES] for mkt in MARKETS]


def run_global_benchmark(
    api_key: str,
    base_url: str,
    model: str,
    runs: int = 2,
    temperature: float = 0.2,
    timeout: int = CONTROL_TIMEOUT_SECONDS,
    mode: str = "lite",
    on_progress: Callable[[dict], None] | None = None,
) -> dict:
    """Run the top-AI control prompt through one OpenAI-compatible endpoint.

    The page-level AI config (api_key/base_url/model) is used instead of
    per-provider environment variables. Lite mode sends one compact request
    per run; full mode splits all combos into market batches so the 23,760-cell
    protocol stays within provider request limits. Responses are stored under
    the ``global`` model key and scored with the regular pipeline so the result
    lands in ``output/control/control_metrics.json``.
    """
    api_key = str(api_key or "").strip()
    base_url = str(base_url or "https://api.deepseek.com/v1").strip()
    model = str(model or "").strip()
    mode = str(mode or "lite").strip().lower()
    if mode not in CONTROL_MODES:
        raise ValueError(f"mode 只能是 lite 或 full：{mode}")
    if not api_key:
        raise ValueError("缺少 API Key")
    if not model:
        raise ValueError("缺少模型名称")
    runs = max(1, min(4, int(runs)))
    batches = _control_batches(mode)
    scope = _control_scope(mode)
    label = f"全局 AI（{model}）"

    out_dir = RESPONSES_DIR / "global"
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("run*_b*.md"):
        old.unlink()
    for old in out_dir.glob("run*_b*.meta.json"):
        old.unlink()
    for old in out_dir.glob("run*_attempt*.md"):
        old.unlink()
    for run in (1, 2):
        (out_dir / f"run{run}.md").unlink(missing_ok=True)
        (out_dir / f"run{run}.meta.json").unlink(missing_ok=True)

    github_signals_file = str(GITHUB_SIGNALS_JSON)
    github_signals_sha = (
        _sha256(GITHUB_SIGNALS_JSON) if GITHUB_SIGNALS_JSON.exists() else ""
    )
    for run in range(1, runs + 1):
        combined = ""
        attempts = 0
        completeness: dict[str, object] = {}
        while attempts < CONTROL_RETRY_LIMIT:
            attempts += 1
            parts: list[str] = []
            for batch_index, combos in enumerate(batches, start=1):
                content = _user_content(combos)
                text = _call_openai_compatible(
                    api_key,
                    base_url,
                    model,
                    content,
                    temperature=temperature,
                    timeout=timeout,
                )
                batch_md = out_dir / f"run{run}_b{batch_index:02d}.md"
                batch_md.write_text(text, encoding="utf-8")
                batch_meta = {
                    "model": "global",
                    "label": label,
                    "api_model_id": model,
                    "base_url": base_url,
                    "run": run,
                    "attempt": attempts,
                    "mode": mode,
                    "scope": scope,
                    "batch_index": batch_index,
                    "batch_total": len(batches),
                    "combos": [list(c) for c in combos],
                    "source": "api",
                    "temperature": temperature,
                    "code_execution": False,
                    "timestamp_utc": pd.Timestamp.utcnow().isoformat(timespec="seconds"),
                    "prompt_file": str(PROMPT_MD),
                    "prompt_sha256": _sha256(PROMPT_MD),
                    "train_csv": str(TRAIN_CSV),
                    "train_csv_sha256": _sha256(TRAIN_CSV),
                }
                (out_dir / f"run{run}_b{batch_index:02d}.meta.json").write_text(
                    json.dumps(batch_meta, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                parts.append(f"## 批次 {batch_index}/{len(batches)}\n\n{text}\n")
                if on_progress is not None:
                    on_progress(
                        {
                            "run": run,
                            "total_runs": runs,
                            "attempt": attempts,
                            "batch": batch_index,
                            "total_batches": len(batches),
                            "mode": mode,
                        }
                    )
            combined = "\n".join(parts).strip() + "\n"
            (out_dir / f"run{run}_attempt{attempts}.md").write_text(
                combined, encoding="utf-8"
            )
            completeness = section_completeness(combined, _holdout_dates())
            if completeness["complete"]:
                break
        (out_dir / f"run{run}.md").write_text(combined, encoding="utf-8")
        meta = {
            "model": "global",
            "label": label,
            "api_model_id": model,
            "base_url": base_url,
            "run": run,
            "mode": mode,
            "scope": scope,
            "batch_total": len(batches),
            "attempts": attempts,
            "completeness": completeness,
            "source": "api",
            "temperature": temperature,
            "code_execution": False,
            "timestamp_utc": pd.Timestamp.utcnow().isoformat(timespec="seconds"),
            "prompt_file": str(PROMPT_MD),
            "prompt_sha256": _sha256(PROMPT_MD),
            "train_csv": str(TRAIN_CSV),
            "train_csv_sha256": _sha256(TRAIN_CSV),
            "github_signals_file": github_signals_file,
            "github_signals_sha256": github_signals_sha,
        }
        (out_dir / f"run{run}.meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return score_all(["global"])


def _predictions_from_text(text: str, holdout_dates: list[str]) -> pd.DataFrame:
    rows = [r for r in extract_forecast_table(text, holdout_dates) if r["date"] in set(holdout_dates)]
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["category", "market", "date", "value"])
    return df.drop_duplicates(["category", "market", "date"], keep="first")


def _pearson(x: pd.Series, y: pd.Series) -> float | None:
    if len(x) < 2 or x.std() == 0 or y.std() == 0:
        return None
    return round(float(np.corrcoef(x, y)[0, 1]), 4)


def _per_combo_mae(
    predictions: pd.DataFrame,
    holdout: pd.DataFrame,
) -> pd.Series:
    if predictions.empty or holdout.empty:
        return pd.Series(dtype=float)
    predictions = predictions.copy()
    predictions["date"] = pd.to_datetime(predictions["date"])
    merged = predictions.merge(
        holdout[["category", "market", "date", "sales_volume"]],
        on=["category", "market", "date"],
        how="inner",
    )
    if merged.empty:
        return pd.Series(dtype=float)
    merged["abs_error"] = (merged["value"] - merged["sales_volume"]).abs()
    return merged.groupby(["category", "market"], sort=False)["abs_error"].mean()


def _aligned_mae_pairs(
    system_mae: pd.Series,
    ai_mae: pd.Series,
) -> tuple[np.ndarray, np.ndarray]:
    """显式 inner-join 对齐系统与 AI 的按品类/市场 MAE，替代双 reindex/dropna。

    配对口径一目了然：只保留两边都有的（品类, 市场）组合，顺序跟随系统侧。
    """
    common_index = system_mae.index.intersection(ai_mae.index)
    common = system_mae.loc[common_index].to_numpy(dtype=float)
    ai_common = ai_mae.loc[common_index].to_numpy(dtype=float)
    mask = ~(np.isnan(common) | np.isnan(ai_common))
    return common[mask], ai_common[mask]


def _representative_run(entry: dict) -> str | None:
    """返回宏 MAE 最低的完整 run；无完整 run 时返回 None（防 cherry-pick 用固定规则）。"""
    best: str | None = None
    best_mae = float("inf")
    for run, run_result in (entry.get("runs") or {}).items():
        if not run_result.get("complete"):
            continue
        mae = run_result.get("mae_macro")
        if mae is None:
            continue
        if float(mae) < best_mae:
            best_mae = float(mae)
            best = run
    return best


def _model_mae_series(
    model_key: str,
    run: str,
    holdout: pd.DataFrame,
) -> pd.Series:
    """重新解析某模型某 run 的存档回复，得到按品类/市场配对的宏 MAE 序列。"""
    md_path = RESPONSES_DIR / model_key / f"run{run}.md"
    if not md_path.exists():
        return pd.Series(dtype=float)
    text = md_path.read_text(encoding="utf-8")
    holdout_dates = sorted(holdout["date"].dt.strftime("%Y-%m-%d").unique().tolist())
    predictions = _predictions_from_text(text, holdout_dates)
    return _per_combo_mae(predictions, holdout)


def compute_significance_tests(payload: dict, *, alpha: float = ALPHA) -> dict:
    """计算对照组显著性全族检验并返回结构化结果（供 significance_report.md 使用）。

    - A 组：各模型各完整 run 的宏 MAE vs 系统 LightGBM 基线（按品类/市场配对）。
    - B 组：模型两两比较，各取宏 MAE 最低的 run 为代表（``_representative_run``）。
    - 全族（A+B）p 值统一做一次 Benjamini-Hochberg 校正，``significant`` 以 q<alpha 为准。
    """
    holdout = pd.read_csv(HOLDOUT_CSV, parse_dates=["date"])
    system_mae = _system_mae_by_combo()
    models = payload.get("models") or {}
    tests: list[dict] = []

    def _append_test(base: dict, sig: dict) -> None:
        tests.append(
            {
                **base,
                "method": sig["method"],
                "n": sig["n"],
                "n_zero_diffs": sig["n_zero_diffs"],
                "mean_difference": sig["mean_difference"],
                "effect_size": sig["effect_size"],
                "p_value": sig["p_value"],
                "degenerate": sig["degenerate"],
            }
        )

    # A 组：AI vs 系统基线
    for model_key, entry in models.items():
        for run in sorted(entry.get("runs") or {}, key=int):
            run_result = entry["runs"][run]
            if not run_result.get("complete"):
                continue
            ai_mae = _model_mae_series(model_key, run, holdout)
            if ai_mae.empty or system_mae.empty:
                continue
            common, ai_common = _aligned_mae_pairs(system_mae, ai_mae)
            if len(common) < 3:
                continue
            sig = paired_significance(common, ai_common, alpha=alpha)
            if sig:
                _append_test(
                    {
                        "group": "A",
                        "model_key": model_key,
                        "run": int(run),
                        "left": "系统基线(LightGBM)",
                        "right": _model_label(model_key, entry),
                        "run_left": None,
                        "run_right": int(run),
                    },
                    sig,
                )

    # B 组：模型两两比较（各取宏 MAE 最低 run 为代表）
    model_keys = list(models)
    for index, left_key in enumerate(model_keys):
        for right_key in model_keys[index + 1 :]:
            left_run = _representative_run(models[left_key])
            right_run = _representative_run(models[right_key])
            if left_run is None or right_run is None:
                continue
            left_mae = _model_mae_series(left_key, left_run, holdout)
            right_mae = _model_mae_series(right_key, right_run, holdout)
            if left_mae.empty or right_mae.empty:
                continue
            common, right_common = _aligned_mae_pairs(left_mae, right_mae)
            if len(common) < 3:
                continue
            sig = paired_significance(common, right_common, alpha=alpha)
            if sig:
                _append_test(
                    {
                        "group": "B",
                        "left_key": left_key,
                        "right_key": right_key,
                        "run_left": int(left_run),
                        "run_right": int(right_run),
                        "left": _model_label(left_key, models[left_key]),
                        "right": _model_label(right_key, models[right_key]),
                    },
                    sig,
                )

    # 全族一次 BH 校正
    p_values = [t["p_value"] for t in tests]
    q_values = bh_adjust(p_values)
    for test, q in zip(tests, q_values):
        test["q_value"] = q
        test["significant"] = bool(q < alpha)

    return {
        "generated_at": pd.Timestamp.utcnow().isoformat(timespec="seconds"),
        "alpha": alpha,
        "adjustment": "benjamini_hochberg",
        "n_tests": len(tests),
        "n_significant": sum(1 for t in tests if t["significant"]),
        "n_degenerate": sum(1 for t in tests if t["degenerate"]),
        "tests": tests,
    }


def _significance_report_markdown(payload: dict) -> str:
    """把 payload["significance"] 渲染为独立显著性报告 markdown。"""
    report = payload.get("significance") or {}
    tests = report.get("tests") or []
    lines = [
        "# 对照组显著性报告",
        "",
        f"- 生成时间：{report.get('generated_at', '—')}",
        f"- 校正方法：{report.get('adjustment', 'benjamini_hochberg')}（全族一次 FDR 校正）",
        f"- 阈值：q < {report.get('alpha', ALPHA)}",
        f"- 检验总数：{report.get('n_tests', 0)}；显著：{report.get('n_significant', 0)}；退化：{report.get('n_degenerate', 0)}",
        "",
        "## A 组：AI vs 系统 LightGBM 基线（按品类/市场配对宏 MAE）",
        "",
        "| 模型 | 运行 | 方法 | 配对组合 n | 零差对 | 均值差(系统-AI) | Cohen's dz | p | q(BH) | 显著 | 退化 |",
        "|------|------|------|-----------|--------|-----------------|-----------|----|-------|------|------|",
    ]
    group_a = [t for t in tests if t["group"] == "A"]
    for t in group_a:
        lines.append(
            "| {right} | run{run} | {method} | {n} | {nzd} | {md:.4g} | {d:.3f} | "
            "{p:.4g} | {q:.4g} | {ok} | {deg} |".format(
                right=t["right"],
                run=t["run"],
                method=t["method"],
                n=t["n"],
                nzd=t["n_zero_diffs"],
                md=t["mean_difference"],
                d=t["effect_size"],
                p=t["p_value"],
                q=t["q_value"],
                ok="是" if t["significant"] else "否",
                deg="是" if t["degenerate"] else "否",
            )
        )
    if not group_a:
        lines.append("| （无足够配对数据） | — | — | — | — | — | — | — | — | — | — |")
    lines.extend(
        [
            "",
            "## B 组：模型两两比较（各取宏 MAE 最低 run 为代表）",
            "",
            "| 模型A | 模型B | runA | runB | 方法 | 配对组合 n | 均值差(A-B) | Cohen's dz | p | q(BH) | 显著 | 退化 |",
            "|-------|-------|------|------|------|-----------|-------------|-----------|----|-------|------|------|",
        ]
    )
    group_b = [t for t in tests if t["group"] == "B"]
    for t in group_b:
        lines.append(
            "| {left} | {right} | run{run_left} | run{run_right} | {method} | {n} | "
            "{md:.4g} | {d:.3f} | {p:.4g} | {q:.4g} | {ok} | {deg} |".format(
                left=t["left"],
                right=t["right"],
                run_left=t["run_left"],
                run_right=t["run_right"],
                method=t["method"],
                n=t["n"],
                md=t["mean_difference"],
                d=t["effect_size"],
                p=t["p_value"],
                q=t["q_value"],
                ok="是" if t["significant"] else "否",
                deg="是" if t["degenerate"] else "否",
            )
        )
    if not group_b:
        lines.append("| （暂无多模型可比较） | — | — | — | — | — | — | — | — | — | — | — |")
    lines.extend(
        [
            "",
            "## 说明",
            "",
            "- 配对组合 n：两方在相同（品类, 市场）上的 MAE 对数。",
            "- 零差对：Wilcoxon 排名中保留的零差对数量（pratt 法，避免样本量虚降）。",
            "- 退化：全零差或零方差时检验统计量无定义，按 p=1 标记 degenerate。",
            "- BH 校正后部分原始显著结论可能降级，属多重比较下的预期行为，以 q 值为准。",
        ]
    )
    return "\n".join(lines) + "\n"


def score_all(models: list[str] | None = None) -> dict:
    """扫描 responses 目录，评分所有已保存回复并写出结果。"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    holdout = pd.read_csv(HOLDOUT_CSV, parse_dates=["date"])
    train = pd.read_csv(TRAIN_CSV, parse_dates=["date"])
    holdout_dates = sorted(holdout["date"].dt.strftime("%Y-%m-%d").unique().tolist())

    if RECOMMEND_CSV.exists():
        recs = pd.read_csv(RECOMMEND_CSV)
        recs = recs.sort_values("rank") if "rank" in recs.columns else recs
    else:
        recs = pd.DataFrame(columns=["category", "market", "rank"])

    targets = models or (["global"] + list(MODEL_REGISTRY))
    results: dict[str, dict] = {}
    for model_key in targets:
        out_dir = RESPONSES_DIR / model_key
        meta: dict = {}
        meta_path = out_dir / "run1.meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                meta = {}
        scope = meta.get("scope") or {}
        holdout_for_model = holdout
        scope_combos: set[tuple[str, str]] | None = None
        if scope.get("mode") == "lite":
            lite_combos = {tuple(c) for c in scope.get("combos") or []}
            if lite_combos:
                scope_combos = lite_combos
                keys = list(zip(holdout["category"], holdout["market"]))
                mask = pd.Series([key in lite_combos for key in keys], index=holdout.index)
                holdout_for_model = holdout[mask]
                scope["total_cells"] = int(len(holdout_for_model)) or int(
                    scope.get("total_cells") or 0
                )
        system_top5 = _top_combos(recs, scope_combos)
        actual_top5 = _actual_top5(holdout_for_model)
        train_for_model = train
        if scope_combos:
            train_keys = list(zip(train["category"], train["market"]))
            train_mask = pd.Series(
                [key in scope_combos for key in train_keys],
                index=train.index,
            )
            train_for_model = train[train_mask]
        runs: dict[str, dict] = {}
        pred_frames: dict[str, pd.DataFrame] = {}
        for run in (1, 2):
            md_path = out_dir / f"run{run}.md"
            if not md_path.exists():
                continue
            text = md_path.read_text(encoding="utf-8")
            scored = score_response(
                text,
                holdout_for_model,
                train_for_model,
                system_top5,
                actual_top5,
                model=model_key,
                run=run,
            )
            runs[str(run)] = scored
            if scored.get("complete"):
                pred_frames[str(run)] = _predictions_from_text(text, holdout_dates)
            else:
                pred_frames[str(run)] = pd.DataFrame(
                    columns=["category", "market", "date", "value"]
                )
        if not runs:
            continue
        info = MODEL_REGISTRY.get(model_key) or {}
        entry: dict = {
            "label": str(meta.get("label") or info.get("label") or model_key),
            "api_model_id": str(
                meta.get("api_model_id") or info.get("default_model") or ""
            ).strip(),
            "base_url": str(meta.get("base_url") or "").strip(),
            "source": str(meta.get("source") or "").strip(),
            "runs": runs,
        }
        if scope:
            entry["scope"] = scope
        complete_runs = [
            str(run)
            for run, run_result in runs.items()
            if run_result.get("complete")
        ]
        if len(complete_runs) == 2:
            p1, p2 = pred_frames[complete_runs[0]], pred_frames[complete_runs[1]]
            merged = p1.merge(p2, on=["category", "market", "date"], suffixes=("_1", "_2"))
            rec1 = set(runs[complete_runs[0]]["recommendations"])
            rec2 = set(runs[complete_runs[1]]["recommendations"])
            rec_union = rec1 | rec2
            entry["reproducibility"] = {
                "forecast_correlation": _pearson(merged["value_1"], merged["value_2"]) if len(merged) else None,
                "common_cells": int(len(merged)),
                "recommendation_jaccard": round(len(rec1 & rec2) / len(rec_union), 4) if rec_union else None,
            }
        system_mae = _system_mae_by_combo()
        if not system_mae.empty:
            significance: dict[str, dict] = {}
            for run, pred_frame in pred_frames.items():
                if not runs[run].get("complete"):
                    continue
                ai_mae = _per_combo_mae(pred_frame, holdout)
                if ai_mae.empty:
                    continue
                common, ai_common = _aligned_mae_pairs(system_mae, ai_mae)
                if len(common) >= 3:
                    sig = paired_significance(common, ai_common)
                    if sig:
                        significance[run] = sig
            if significance:
                entry["significance_vs_system"] = significance
        results[model_key] = entry

    baseline = baseline_means()
    first_scope = next(
        (entry.get("scope") for entry in results.values() if entry.get("scope")),
        None,
    )
    payload: dict = {
        "generated_at": pd.Timestamp.utcnow().isoformat(timespec="seconds"),
        "train_dates": f"{train['date'].min().date()} ~ {train['date'].max().date()}",
        "holdout_dates": f"{holdout['date'].min().date()} ~ {holdout['date'].max().date()}",
        "total_cells": int(len(holdout)),
        "system_baseline": baseline,
        "github_signals": {
            "file": str(GITHUB_SIGNALS_JSON),
            "sources": (load_github_signals(GITHUB_SIGNALS_JSON).get("sources") or {}),
        },
        "models": results,
    }
    if first_scope:
        payload["scope"] = first_scope
    significance_report = compute_significance_tests(payload)
    payload["significance"] = significance_report
    for test in significance_report["tests"]:
        if test["group"] == "A":
            entry = payload["models"].get(test["model_key"])
            run_key = str(test["run"])
            if entry and run_key in entry.get("significance_vs_system", {}):
                sig = entry["significance_vs_system"][run_key]
                sig["q_value"] = test["q_value"]
                sig["significant"] = test["significant"]
    json_path = OUTPUT_DIR / "control_metrics.json"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT_DIR / "score_summary.md").write_text(
        _summary_markdown(payload), encoding="utf-8"
    )
    (OUTPUT_DIR / "significance_report.md").write_text(
        _significance_report_markdown(payload), encoding="utf-8"
    )
    return payload


def _model_label(model_key: str, entry: dict) -> str:
    label = str(entry.get("label") or "").strip()
    if label:
        return label
    info = MODEL_REGISTRY.get(model_key)
    return str(info["label"]) if info else model_key


def _summary_markdown(payload: dict) -> str:
    scope = payload.get("scope") or {}
    scope_combos = scope.get("combos") or []
    if scope.get("mode") == "lite" and scope_combos:
        summary_combo_count = len(scope_combos)
        summary_cells = int(scope.get("total_cells") or payload["total_cells"])
    else:
        summary_combo_count = COMBO_COUNT
        summary_cells = int(payload["total_cells"])
    lines = [
        "# 顶级 AI 对照组评分汇总",
        "",
        f"- 训练集：{payload['train_dates']}（共 {summary_combo_count} 组合 × {TEST_WEEKS} 周 = {summary_cells} 个预测格子）",
        f"- 隐藏测试集：{payload['holdout_dates']}",
        f"- 系统基线：Prophet MAPE {payload['system_baseline']['prophet_mape']}% / LightGBM MAPE {payload['system_baseline']['lightgbm_mape']}%",
        "",
    ]
    if scope.get("mode") == "lite":
        lines.append(
            f"- 全局 AI 对照口径：轻量 {len(scope_combos)} 组合 × "
            f"{TEST_WEEKS} 周 = {summary_cells} 格"
        )
    elif scope.get("mode") == "full":
        lines.append(
            f"- 全局 AI 对照口径：完整 {COMBO_COUNT} 组合 × {TEST_WEEKS} 周 = "
            f"{scope.get('total_cells') or payload['total_cells']} 格"
        )
    github_signals = payload.get("github_signals") or {}
    if github_signals.get("sources"):
        lines.append("- GitHub 真实信号覆盖：")
        for provider, info in github_signals["sources"].items():
            lines.append(
                f"  - {provider}: raw={info.get('raw_rows')}, "
                f"mapped={info.get('mapped_rows')}, skipped={info.get('skipped_rows')}"
            )
    lines.extend(
        [
            "",
            "| 模型 | 运行 | 覆盖格数 | 完整率 | MAPE(宏平均) | MAE(宏平均) | 幻觉待核验 | Top5命中 | 备货建议 | 置信/风险 | 假设说明 |",
            "|------|------|---------|--------|-------------|-------------|-----------|----------|---------|-----------|----------|",
        ]
    )
    for model_key, entry in payload["models"].items():
        for run, m in entry["runs"].items():
            g = m["grounding"]
            if m.get("complete"):
                g_text = f"{g.get('claims_total', '—')} 候选 / {g.get('claims_ungrounded', 0)} 待核验"
                hits_system = m.get("recommendation_hits_system")
                hits_actual = m.get("recommendation_hits_actual")
                if hits_system is not None and hits_actual is not None:
                    hits_text = f"{m['recommendation_hits']}（系统 {hits_system}/真实 {hits_actual}）"
                else:
                    hits_text = m["recommendation_hits"]
                lines.append(
                    "| {label} | run{run} | {cells} | {cov}% | {mape} | {mae} | {g} | {hits} | {inv} | {unc} | {ass} |".format(
                        label=_model_label(model_key, entry),
                        run=run,
                        cells=m["forecast_cells"],
                        cov=round(m["coverage"] * 100, 2),
                        mape="—" if m["mape_macro"] is None else f"{m['mape_macro']}%",
                        mae="—" if m["mae_macro"] is None else f"{m['mae_macro']}",
                        g=g_text,
                        hits=hits_text,
                        inv="是" if m["has_inventory"] else "否",
                        unc="是" if m["has_uncertainty"] else "否",
                        ass="是" if m["has_assumptions"] else "否",
                    )
                )
            else:
                missing = "、".join((m.get("sections") or {}).get("missing") or [])
                lines.append(
                    f"| {_model_label(model_key, entry)} | run{run} | "
                    f"失败（缺 {missing}） | — | — | — | — | — | — | — | — |"
                )
    lines.append("")
    lines.append("复现性（run1 vs run2）：")
    lines.append("")
    lines.append("| 模型 | 预测相关系数 | 共同格子 | Top5 Jaccard |")
    lines.append("|------|-------------|---------|--------------|")
    any_rep = False
    for model_key, entry in payload["models"].items():
        rep = entry.get("reproducibility")
        if not rep:
            continue
        any_rep = True
        lines.append(
            "| {label} | {corr} | {cells} | {jacc} |".format(
                label=_model_label(model_key, entry),
                corr="—" if rep["forecast_correlation"] is None else rep["forecast_correlation"],
                cells=rep["common_cells"],
                jacc="—" if rep["recommendation_jaccard"] is None else rep["recommendation_jaccard"],
            )
        )
    if not any_rep:
        lines.append("| （尚无完整两次运行） | — | — | — |")
    lines.append("")
    lines.append(
        "显著性（系统 LightGBM 基线 vs AI，按品类/市场配对 MAE；"
        "显著以 BH 校正后 q<0.05 为准，详见 significance_report.md）："
    )
    lines.append("")
    lines.append("| 模型 | 运行 | 方法 | 配对 n | p 值 | q(BH) | Cohen's dz | 显著 |")
    lines.append("|------|------|------|--------|------|-------|-----------|------|")
    any_sig = False
    for model_key, entry in payload["models"].items():
        significance = entry.get("significance_vs_system") or {}
        for run, sig in significance.items():
            any_sig = True
            q_value = sig.get("q_value")
            lines.append(
                "| {label} | run{run} | {method} | {n} | {p} | {q} | {d} | {ok} |".format(
                    label=_model_label(model_key, entry),
                    run=run,
                    method=sig["method"],
                    n=sig.get("n", "—"),
                    p=f"{sig['p_value']:.4g}",
                    q="—" if q_value is None else f"{q_value:.4g}",
                    d=f"{sig['effect_size']:.3f}",
                    ok="是" if sig["significant"] else "否",
                )
            )
    if not any_sig:
        lines.append("| （尚无足够配对数据） | — | — | — | — | — | — | — |")
    lines.append("")
    lines.append("> 幻觉待核验 = 未在原始数据中直接匹配到的数字数量，需人工复核是否为派生统计或编造。")
    return "\n".join(lines) + "\n"
