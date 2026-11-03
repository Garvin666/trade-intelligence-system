"""跨境电商智能选品决策系统 — Streamlit 可视化看板。"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.config import (
    CATEGORIES,
    DATA_STATUS_JSON,
    FORECAST_CSV,
    MARKETS,
    PROCESSED_CSV,
    RECOMMEND_CSV,
    WEEKS_HISTORY,
    category_name,
    market_name,
)
from src.trade.compliance import ComplianceAssessor
from src.trade.conflict import resolve_trade_conflict
from src.trade.cost import (
    LOGISTICS_OPTIONS,
    PAYMENT_CHANNELS,
    LandedCostCalculator,
    LandedCostInput,
)
from src.trade.credit import CreditAssessor
from src.trade.decision import build_trade_decision
from src.trade.green import GreenAssessor
from src.trade.hs_code import lookup_hs
from src.trade.ip import IpScreener
from src.trade.logistics import FreightForecaster
from src.trade.osint import assess_osint
from src.trade.policy import BASE_TARIFF_RATE, evaluate_policy
from src.trade.preflight import build_preflight
from src.trade.sentiment import SentimentAnalyzer
from src.trade.report import build_selection_report

COMBO_COUNT = len(CATEGORIES) * len(MARKETS)


@st.cache_data(show_spinner=False)
def load_history() -> pd.DataFrame:
    if PROCESSED_CSV.exists():
        df = pd.read_csv(PROCESSED_CSV)
        df["date"] = pd.to_datetime(df["date"])
        return df
    return pd.DataFrame()


@st.cache_data(show_spinner=False)
def load_forecast() -> pd.DataFrame:
    if FORECAST_CSV.exists():
        df = pd.read_csv(FORECAST_CSV)
        df["date"] = pd.to_datetime(df["date"])
        return df
    return pd.DataFrame()


@st.cache_data(show_spinner=False)
def load_recommendations() -> pd.DataFrame:
    if RECOMMEND_CSV.exists():
        return pd.read_csv(RECOMMEND_CSV)
    return pd.DataFrame()


def _normalize(series: pd.Series) -> pd.Series:
    """min-max 归一化到 0-100，便于多源数据叠加对比。"""
    rng = series.max() - series.min()
    if rng == 0 or series.isna().all():
        return pd.Series(50.0, index=series.index)
    return (series - series.min()) / rng * 100


def _chart_layout(
    fig: go.Figure,
    title: str,
    x_title: str | None = None,
    y_title: str | None = None,
    height: int = 420,
    hovermode: str = "x unified",
    **kwargs,
) -> go.Figure:
    """统一图表细节：顶部水平图例、紧凑边距、悬停模式与标题锚点。"""
    layout = dict(
        title=dict(text=title, x=0.02, xanchor="left", font=dict(size=15, color="#E8EEF6")),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#E8EEF6"),
        xaxis=dict(
            title=dict(text=x_title),
            gridcolor="rgba(148,163,184,.15)",
            zerolinecolor="rgba(148,163,184,.15)",
        ),
        yaxis=dict(
            title=dict(text=y_title),
            gridcolor="rgba(148,163,184,.15)",
            zerolinecolor="rgba(148,163,184,.15)",
        ),
        height=height,
        hovermode=hovermode,
        margin=dict(l=10, r=10, t=60, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0.02, xanchor="left"),
    )
    layout.update(kwargs)
    fig.update_layout(**layout)
    return fig


def _trend_chart(df: pd.DataFrame, category: str, market: str) -> go.Figure:
    sub = df[(df["category"] == category) & (df["market"] == market)].sort_values("date")
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=sub["date"],
            y=_normalize(sub["sales_volume"]),
            name="销量指数（归一化）",
            line=dict(color="#22D3EE", width=2),
            hovertemplate="%{x|%Y-%m-%d}<br>销量指数（归一化）：%{y:.1f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=sub["date"],
            y=sub["search_index"],
            name="搜索热度",
            line=dict(color="#F59E0B", width=2, dash="dot"),
            hovertemplate="%{x|%Y-%m-%d}<br>搜索热度：%{y:.1f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=sub["date"],
            y=_normalize(sub["export_value"]),
            name="出口金额（归一化）",
            line=dict(color="#34D399", width=2, dash="dash"),
            hovertemplate="%{x|%Y-%m-%d}<br>出口金额（归一化）：%{y:.1f}<extra></extra>",
        )
    )
    return _chart_layout(
        fig,
        title=f"{category_name(category)} × {market_name(market)} 多源热度趋势",
        x_title="日期",
        yaxis_title="指数 / 热度",
        height=420,
    )


def _forecast_chart(history: pd.DataFrame, forecast: pd.DataFrame, category: str, market: str, model: str) -> go.Figure:
    hist = history[(history["category"] == category) & (history["market"] == market)].sort_values("date")
    fc = forecast[
        (forecast["category"] == category)
        & (forecast["market"] == market)
        & (forecast["model"] == model)
    ].sort_values("date")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=hist["date"],
            y=hist["sales_volume"],
            name="历史销量",
            line=dict(color="#94A3B8", width=2),
            hovertemplate="%{x|%Y-%m-%d}<br>历史销量：%{y:.1f} 指数<extra></extra>",
        )
    )
    if not fc.empty:
        fig.add_trace(
            go.Scatter(
                x=fc["date"],
                y=fc["yhat_upper"],
                mode="lines",
                line=dict(width=0),
                showlegend=False,
                hoverinfo="skip",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=fc["date"],
                y=fc["yhat_lower"],
                mode="lines",
                line=dict(width=0),
                fill="tonexty",
                fillcolor="rgba(34, 211, 238, 0.18)",
                name="预测区间",
                hovertemplate="%{x|%Y-%m-%d}<br>预测区间下限：%{y:.1f} 指数<extra>预测区间</extra>",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=fc["date"],
                y=fc["yhat"],
                name="预测销量",
                line=dict(color="#22D3EE", width=2.5, dash="dash"),
                hovertemplate="%{x|%Y-%m-%d}<br>预测销量：%{y:.1f} 指数<extra></extra>",
            )
        )
        fig.add_vline(
            x=fc["date"].min(),
            line_dash="dash",
            line_color="#22D3EE",
            annotation_text="预测起始",
            annotation_position="top right",
            annotation_font_size=11,
            annotation_font_color="#0891B2",
        )
    model_label = "Prophet 基线" if model == "prophet_baseline" else "LightGBM 进阶"
    return _chart_layout(
        fig,
        title=f"{category_name(category)} × {market_name(market)} 未来90天销量预测（{model_label}）",
        x_title="日期",
        yaxis_title="销量指数",
        height=440,
    )


def _market_compare(history: pd.DataFrame) -> go.Figure:
    recent = history[history["date"] >= history["date"].max() - pd.Timedelta(days=84)]
    summary = recent.groupby("market", observed=True).agg(
        avg_sales=("sales_volume", "mean"),
        avg_competition=("competition_index", "mean"),
        avg_price=("price_median", "mean"),
    ).reset_index()
    summary["market_name"] = summary["market"].map(market_name)

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=summary["market_name"],
            y=summary["avg_sales"],
            name="近12周平均销量",
            marker_color="#22D3EE",
            text=summary["avg_sales"].round(1),
            textposition="outside",
            texttemplate="%{text:.1f}",
            hovertemplate="%{x}<br>近12周平均销量：%{y:.1f} 指数<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            x=summary["market_name"],
            y=summary["avg_competition"],
            name="平均竞争度",
            marker_color="#F59E0B",
            text=summary["avg_competition"].round(1),
            textposition="outside",
            texttemplate="%{text:.1f}",
            hovertemplate="%{x}<br>平均竞争度：%{y:.1f} / 100<extra></extra>",
        )
    )
    fig.update_layout(barmode="group")
    return _chart_layout(
        fig,
        title="市场对比：近12周销量与竞争度",
        x_title="市场",
        yaxis_title="指数",
        height=420,
    )


def _analysis_charts(
    history: pd.DataFrame,
    forecast: pd.DataFrame,
    recommendations: pd.DataFrame,
) -> None:
    """数据分析页签：探索性分析、模型评估与推荐构成。"""
    st.subheader("数据规模")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("历史数据", f"{len(history)} 条")
    c2.metric("时间跨度", f"{history['date'].nunique()} 周")
    c3.metric("组合覆盖", f"{history['category'].nunique()} × {history['market'].nunique()}")
    c4.metric("预测行数", f"{len(forecast)} 行")

    st.subheader("品类 × 市场平均销量")
    pivot = history.pivot_table(
        index="category", columns="market", values="sales_volume", aggfunc="mean"
    )
    pivot.index = [category_name(code) for code in pivot.index]
    pivot.columns = [market_name(code) for code in pivot.columns]
    heat = px.imshow(
        pivot,
        text_auto=".1f",
        color_continuous_scale=["#101826", "#0E7490", "#22D3EE", "#67E8F9"],
        aspect="auto",
        title="品类 × 市场平均销量指数",
    )
    heat.update_coloraxes(colorbar=dict(title="平均销量指数"))
    heat.update_xaxes(title="市场")
    heat.update_yaxes(title="品类")
    heat.update_layout(margin=dict(l=10, r=10, t=60, b=10), height=460)
    heat.update_traces(hovertemplate="%{y} × %{x}：%{z:.1f} 指数<extra></extra>")
    st.plotly_chart(heat, use_container_width=True)

    st.subheader("周粒度季节性")
    weekly = history.copy()
    weekly["week"] = weekly["date"].dt.isocalendar().week.astype(int)
    weekly_avg = weekly.groupby("week")["sales_volume"].mean().reset_index()
    fig = px.line(
        weekly_avg,
        x="week",
        y="sales_volume",
        markers=True,
        title="跨组合平均销量（按 ISO 周）",
        labels={"week": "ISO 周", "sales_volume": "平均销量"},
    )
    fig.update_traces(line=dict(color="#22D3EE", width=2.2), marker=dict(color="#22D3EE", size=5))
    fig.update_traces(hovertemplate="第 %{x} 周：%{y:.1f} 指数<extra>平均销量</extra>")
    fig.add_hline(
        y=weekly_avg["sales_volume"].mean(),
        line_dash="dash",
        line_color="#F59E0B",
        annotation_text=f"均值 {weekly_avg['sales_volume'].mean():.1f}",
        annotation_position="top right",
        annotation_font_size=11,
    )
    _chart_layout(fig, "跨组合平均销量（按 ISO 周）", x_title="ISO 周", y_title="平均销量（指数）", height=360)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("双模型误差对比")
    try:
        from src.config import METRICS_JSON
        import json

        metrics = json.loads(METRICS_JSON.read_text(encoding="utf-8"))
        baseline = pd.DataFrame(metrics.get("baseline", []))
        advanced = pd.DataFrame(metrics.get("advanced", []))
        if not baseline.empty and not advanced.empty:
            compare = baseline[["category", "market", "mape"]].rename(columns={"mape": "Prophet 基线"})
            compare["LightGBM 进阶"] = advanced["mape"].values
            compare["组合"] = compare["category"].map(category_name) + " × " + compare["market"].map(market_name)
            melted = compare.melt(
                id_vars="组合",
                value_vars=["Prophet 基线", "LightGBM 进阶"],
                var_name="模型",
                value_name="MAPE%",
            )
            fig = px.bar(
                melted,
                x="组合",
                y="MAPE%",
                color="模型",
                barmode="group",
                title=f"双模型 MAPE 对比（{COMBO_COUNT} 组合）",
                color_discrete_map={"Prophet 基线": "#94A3B8", "LightGBM 进阶": "#22D3EE"},
                text=melted["MAPE%"].round(1),
            )
            fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig.update_traces(hovertemplate="<b>%{x}</b><br>%{fullData.name}：%{y:.1f}%<extra></extra>")
            _chart_layout(
                fig,
                f"双模型 MAPE 对比（{COMBO_COUNT} 组合）",
                x_title="组合",
                y_title="MAPE（%）",
                height=440,
            )
            fig.update_xaxes(tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
    except Exception:  # noqa: BLE001 - 指标文件缺失时跳过
        st.info("模型指标文件缺失，请先运行 `scripts/run_pipeline.py`。")

    st.subheader("Top 10 推荐评分构成")
    if not recommendations.empty:
        top10 = recommendations.sort_values("rank").head(10).copy()
        top10["组合"] = top10["category"].map(category_name) + " × " + top10["market"].map(market_name)
        top10["竞争反向"] = 100 - top10["competition"]
        top10_melt = top10.melt(
            id_vars="组合",
            value_vars=["forecast_growth", "search_trend", "竞争反向", "review_growth"],
            var_name="维度",
            value_name="数值",
        )
        fig = px.bar(
            top10_melt,
            x="组合",
            y="数值",
            color="维度",
            title="Top 10 推荐评分构成（原始指标）",
            color_discrete_map={
                "forecast_growth": "#22D3EE",
                "search_trend": "#F59E0B",
                "竞争反向": "#34D399",
                "review_growth": "#E879F9",
            },
            labels={"forecast_growth": "预测增长", "search_trend": "搜索趋势", "review_growth": "评论增长"},
        )
        fig.update_traces(hovertemplate="<b>%{x}</b><br>%{fullData.name}：%{y:.1f}%<extra></extra>")
        _chart_layout(fig, "Top 10 推荐评分构成（原始指标）", x_title="组合", y_title="评分维度值（%）", height=440)
        fig.update_xaxes(tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)


def _rule_conclusion(results: list[dict], query: str) -> str:
    if not results:
        return f"未获取到“{query}”的搜索结果。"
    valid = [r for r in results if r.get("link")]
    topics = "；".join((r.get("title") or r.get("snippet") or "")[:60] for r in results[:3])
    return (
        f"针对“{query}”共检索到 {len(results)} 条结果（含有效链接 {len(valid)} 条）。"
        f"主要信息：{topics}。建议人工核验来源后引用，联网失败时结果已标注模拟回退。"
    )


def _ai_conclusion(query: str, ai_settings: dict | None = None) -> str:
    try:
        from src.api import brain_bridge

        has_key = bool((ai_settings or {}).get("api_key")) or bool(os.environ.get("OPENAI_API_KEY"))
        if brain_bridge.available() and has_key:
            payload = {"keyword": query, "research": True, "search_provider": "crawler"}
            if ai_settings:
                payload.update({key: value for key, value in ai_settings.items() if value not in (None, "")})
            result = brain_bridge.analyze(
                payload,
                use_ai=True,
            )
            research = result.get("research") or {}
            if research.get("summary"):
                return str(research["summary"])
    except Exception:  # noqa: BLE001 - AI 失败回退规则结论
        pass
    return ""


def _daily_status() -> dict:
    if not DATA_STATUS_JSON.exists():
        return {}
    try:
        return json.loads(DATA_STATUS_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _show_daily_status() -> None:
    status = _daily_status()
    online = status.get("online", {})
    parts: list[str] = []
    if status.get("data_as_of"):
        parts.append(f"数据更新至 {status['data_as_of']}（每日自动更新）")
    if online:
        state = "模拟回退" if online.get("fallback_used") else "实时联网"
        parts.append(
            f"联网快照 {state} · {online.get('provider', '-')} · "
            f"{online.get('sources_count', 0)} 条来源"
        )
    crawler = status.get("crawler") or {}
    if crawler.get("status"):
        parts.append(
            f"爬虫信号 {crawler.get('status', 'not_generated')} 路 "
            f"{crawler.get('combos', 0)} 组合 路 {crawler.get('sources_count', 0)} 来源"
        )
    for key, label in (
        ("trends", "Trends"),
        ("platform_rankings", "平台榜单"),
        ("customs", "海关出口"),
        ("anomalies", "异常检测"),
        ("suppliers", "货源/供应商"),
    ):
        block = status.get(key) or {}
        if block.get("enabled"):
            state = "回退" if block.get("fallback_used") else "实时"
            detail = block.get("provider") or block.get("rows") or "-"
            parts.append(f"{label} {state} · {detail}")
    if parts:
        st.caption("｜".join(parts))


def _show_crawler_snapshot() -> None:
    from pathlib import Path

    status = _daily_status().get("crawler") or {}
    if not status.get("status"):
        return
    st.caption(
        f"爬虫信号 {status.get('status', 'not_generated')} 路 "
        f"{status.get('combos', 0)} 组合 路 {status.get('sources_count', 0)} 来源"
    )
    snapshot_path = Path("output/crawler/latest.json")
    if not snapshot_path.exists():
        return
    try:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    for combo in (snapshot.get("combos") or [])[:5]:
        trend = float(combo.get("pageview_trend_pct") or 0)
        links = " · ".join(
            f"[{item.get('title', '来源')}]({item.get('link')})"
            for item in (combo.get("top_sources") or [])[:2]
            if item.get("link")
        )
        label = (
            f"{combo.get('category_name', combo.get('category', ''))} × "
            f"{combo.get('market_name', combo.get('market', ''))} · 趋势 {trend:+.1f}%"
        )
        st.caption(label + (f" · {links}" if links else ""))


def _search_panel(ai_settings: dict | None = None) -> None:
    st.subheader("联网搜索")
    st.caption("默认 DuckDuckGo Lite 无 Key 直连；失败自动回退模拟结果，并标注状态。")
    _show_daily_status()
    _show_crawler_snapshot()
    presets = ["关税政策", "美国 de minimis", "欧盟低价值包裹", "跨境电商品类趋势"]
    cols = st.columns(len(presets))
    for col, tag in zip(cols, presets):
        if col.button(tag, key=f"preset_{tag}"):
            st.session_state["search_query"] = tag
    query = st.text_input(
        "搜索关键词",
        value=st.session_state.get("search_query", ""),
        key="search_query_input",
        placeholder="例如：US de minimis 2026 tariff",
    )
    run = st.button("联网搜索", type="primary")
    if not run:
        return
    keyword = (query or st.session_state.get("search_query", "")).strip()
    if not keyword:
        st.info("请输入搜索关键词。")
        return
    try:
        from src.api.services import web_search

        result = web_search(keyword, max_results=5)
    except Exception as exc:  # noqa: BLE001
        result = {"provider": "mock", "fallback_used": True, "results": [], "error": str(exc)}
    st.session_state["search_result"] = result
    st.session_state["search_query"] = keyword
    results = result.get("results", [])
    provider = result.get("provider", "mock")
    fallback = result.get("fallback_used", False)
    status = "模拟回退" if fallback or provider == "mock" else "实时联网"
    st.write(f"搜索服务：{provider}｜状态：{status}｜结果 {len(results)} 条")
    if results:
        for index, item in enumerate(results):
            with st.container(border=True):
                st.markdown(f"**{item.get('title', '未命名')}**")
                if item.get("link"):
                    st.markdown(f"[打开来源]({item['link']})")
                st.caption(item.get("snippet", "")[:200])
                if st.button("加入证据清单", key=f"ev_{index}_{hash(str(item))}"):
                    st.session_state.setdefault("evidence", []).append(item)
                    st.success("已加入证据清单。")

    if st.button("自动生成结论"):
        conclusion = _ai_conclusion(keyword, ai_settings) or _rule_conclusion(results, keyword)
        st.session_state["search_conclusion"] = conclusion
    if st.session_state.get("search_conclusion"):
        st.info(st.session_state["search_conclusion"])

    evidence = st.session_state.get("evidence", [])
    st.subheader(f"证据清单（{len(evidence)}）")
    if evidence:
        st.dataframe(
            pd.DataFrame(evidence)[["title", "snippet", "link"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("尚未加入证据。")


def _render_trade_tab(history: pd.DataFrame, category: str, market: str) -> None:
    st.subheader(f"{category_name(category)} × {market_name(market)} 贸易决策测算")
    st.caption("决策流程：选品 → 测算 → 风险 → 结论 → 导出")

    default_price = 30.0
    if not history.empty:
        sub = history[(history["category"] == category) & (history["market"] == market)]
        if not sub.empty:
            default_price = float(sub.sort_values("date").iloc[-1]["price_median"])

    c1, c2, c3, c4 = st.columns(4)
    unit_price = c1.number_input(
        "售价（美元）", min_value=1.0, value=round(default_price, 2), step=1.0
    )
    procurement_cny = c2.number_input(
        "采购成本（人民币）",
        min_value=1.0,
        value=round(default_price * 7.15 * 0.35, 2),
        step=1.0,
    )
    payment_code = c3.selectbox(
        "支付通道",
        options=list(PAYMENT_CHANNELS),
        format_func=lambda code: PAYMENT_CHANNELS[code].name,
    )
    logistics_code = c4.selectbox(
        "物流方案",
        options=list(LOGISTICS_OPTIONS),
        format_func=lambda code: LOGISTICS_OPTIONS[code].name,
    )
    product_name = st.text_input(
        "候选品名称（留空按品类默认筛查）", value="", placeholder="例如 SnapContainer"
    )

    calculator = LandedCostCalculator()
    base = calculator.calculate(
        LandedCostInput(
            category=category,
            market=market,
            unit_price_usd=unit_price,
            procurement_cost_cny=procurement_cny,
            payment_code=payment_code,
            logistics_code=logistics_code,
            tariff_rate=BASE_TARIFF_RATE[market][category],
        )
    )
    alert = evaluate_policy(category, market, unit_price, base.landed_cost_usd)
    final = calculator.calculate(
        LandedCostInput(
            category=category,
            market=market,
            unit_price_usd=unit_price,
            procurement_cost_cny=procurement_cny,
            payment_code=payment_code,
            logistics_code=logistics_code,
            tariff_rate=alert.effective_tariff_rate,
            min_duty_usd=alert.min_duty_usd,
        )
    )
    compliance = ComplianceAssessor().assess(market)
    ip_result = IpScreener().screen(category, market, product_name or None)
    freight = FreightForecaster().forecast(market)
    sentiment = SentimentAnalyzer().analyze(market)
    green = GreenAssessor().assess(category, market, unit_price)
    credit = CreditAssessor().assess(
        category,
        market,
        margin_pct=final.margin_pct,
        policy_risk=alert.risk_level,
        freight_risk=freight.risk,
    )
    preflight = build_preflight(
        category,
        market,
        margin_pct=final.margin_pct,
        freight_risk=freight.risk,
        compliance_result=compliance,
    )
    hs = lookup_hs(category, market)
    osint = assess_osint(
        category,
        market,
        financing_ready_score=credit.financing_ready_score,
    )
    growth_score = 50.0 + sentiment.avg_score * 50.0
    conflict = resolve_trade_conflict(
        growth_score=growth_score,
        policy_risk=alert.risk_level,
        freight_risk=freight.risk,
        margin_pct=final.margin_pct,
        feasibility_score=compliance.feasibility_score,
        sentiment_score=sentiment.avg_score,
        financing_score=credit.financing_ready_score,
    )
    st.session_state["trade_summary"] = {
        "category": category,
        "category_name": category_name(category),
        "market": market,
        "market_name": market_name(market),
        "unit_price_usd": unit_price,
        "procurement_cost_cny": procurement_cny,
        "risk_level": alert.risk_level,
        "risk_message": alert.message,
        "margin_pct": final.margin_pct,
        "effective_tariff_rate": alert.effective_tariff_rate,
        "duty_usd_per_unit": final.duty_usd,
        "feasibility_score": compliance.feasibility_score,
        "ip_risk_level": ip_result.risk_level,
        "financing_level": credit.financing_level,
        "conflict_level": conflict.conflict_level,
        "conflict_decision": conflict.decision,
        "preflight_ready": preflight.ready,
        "hs_code": hs["hs_code"],
        "best_logistics": "",
    }

    if alert.risk_level == "high":
        st.error(f"政策风险预警：{alert.message}")
    elif alert.risk_level == "medium":
        st.warning(f"政策风险提示：{alert.message}")
    else:
        st.success(f"政策状态正常：{alert.message}")
    st.caption("应对建议：" + "、".join(alert.actions))
    h1, h2, h3 = st.columns(3)
    h1.metric("默认 HS6", hs["hs_code"] or "-")
    h2.metric("HS 描述", hs["description"] or "-")
    h3.metric("卖前体检", "通过" if preflight.ready else "待确认")
    with st.container(border=True):
        st.markdown("**综合决策结论**")
        risk_label = {"high": "高", "medium": "中", "low": "低"}.get(alert.risk_level, alert.risk_level)
        st.markdown(
            f"风险等级：{risk_label} ｜ "
            f"到岸利润率：{final.margin_pct:.1f}% ｜ 准入可行性：{compliance.feasibility_score:.0f}/100 ｜ "
            f"融资档位：{credit.financing_level}"
        )
        st.markdown(f"冲突裁定：{conflict.decision}")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("政策风险", {"high": "高", "medium": "中", "low": "低"}[alert.risk_level])
    m2.metric("单件关税", f"${final.duty_usd:.2f}")
    m3.metric("到岸利润率", f"{final.margin_pct:.1f}%")
    m4.metric("准入可行性", f"{compliance.feasibility_score:.0f} / 100")

    st.subheader("到岸成本明细")
    breakdown = pd.DataFrame(list(final.breakdown().items()), columns=["项目", "金额（美元）"])
    st.dataframe(breakdown, use_container_width=True, hide_index=True)

    st.subheader("汇率敏感性（人民币兑美元）")
    fx_df = pd.DataFrame(final.fx_sensitivity).T.reset_index().rename(columns={"index": "情景"})
    st.dataframe(fx_df, use_container_width=True, hide_index=True)

    st.subheader("物流运价与时效预测（SCFI 风格演示）")
    f1, f2, f3, f4 = st.columns(4)
    f1.metric("运价指数", f"{freight.index_now:.0f}")
    f2.metric("4 周预测", f"{freight.index_forecast:.0f}")
    f3.metric("运价涨幅", f"{freight.trend_pct:.1f}%")
    f4.metric("交付时效", f"{freight.delivery_days_min}-{freight.delivery_days_max} 天")
    freight_df = pd.DataFrame(
        [
            {
                "航线": freight.lane,
                "当前指数": freight.index_now,
                "4 周预测指数": freight.index_forecast,
                "涨幅%": freight.trend_pct,
                "预测单件物流成本（人民币）": freight.cost_forecast_cny_per_kg,
                "拥堵": {"high": "高", "medium": "中", "low": "低"}[freight.congestion],
                "风险": {"high": "高", "medium": "中", "low": "低"}[freight.risk],
                "说明": freight.note,
            }
        ]
    )
    st.dataframe(freight_df, use_container_width=True, hide_index=True)

    st.subheader("多语言舆情（英 / 西 / 德 / 日 / 葡 演示词库）")
    s1, s2, s3 = st.columns(3)
    s1.metric("平均情绪分", f"{sentiment.avg_score:.2f}")
    s2.metric("整体舆情", {"positive": "正面", "neutral": "中性", "negative": "负面"}[sentiment.overall])
    s3.metric("语言覆盖", f"{len(sentiment.languages)} 种")
    sentiment_df = pd.DataFrame(
        [
            {
                "语言": item.language_name,
                "评论数": item.comment_count,
                "正面": item.positive,
                "中性": item.neutral,
                "负面": item.negative,
                "情绪分": item.score,
                "趋势": {"rising": "上升", "flat": "平稳", "falling": "下滑"}[item.trend],
                "摘要": item.sample_summary,
            }
            for item in sentiment.languages
        ]
    )
    st.dataframe(sentiment_df, use_container_width=True, hide_index=True)
    st.caption(sentiment.recommendation)

    st.subheader("绿色贸易与 CBAM 前瞻")
    g1, g2, g3 = st.columns(3)
    g1.metric("CBAM 暴露度", {"high": "高", "medium": "中", "low": "低"}[green.exposure])
    g2.metric("预估碳成本", f"${green.carbon_cost_usd:.2f}")
    g3.metric("政策趋势", {"rising": "上升", "flat": "平稳"}[green.trend])
    green_df = pd.DataFrame(
        [
            {
                "市场": market_name(market),
                "品类": category_name(category),
                "CBAM 暴露度": {"high": "高", "medium": "中", "low": "低"}[green.exposure],
                "预估碳成本（美元）": green.carbon_cost_usd,
                "政策趋势": {"rising": "上升", "flat": "平稳"}[green.trend],
                "风险": {"high": "高", "medium": "中", "low": "低"}[green.risk],
            }
        ]
    )
    st.dataframe(green_df, use_container_width=True, hide_index=True)
    st.caption(green.recommendation)

    st.subheader("数据信用与供应链金融（离线演示版）")
    c1, c2, c3 = st.columns(3)
    c1.metric("融资就绪分", f"{credit.financing_ready_score:.1f} / 100")
    c2.metric("融资档位", credit.financing_level)
    c3.metric("数据覆盖度", f"{credit.data_coverage_score:.0f} / 100")
    credit_df = pd.DataFrame(
        [
            {
                "订单稳定性": {"high": "高", "medium": "中", "low": "低"}[credit.order_stability],
                "履约率%": credit.completion_rate,
                "退款率%": credit.return_rate,
                "政策风险评分": credit.policy_risk_score,
                "融资就绪分": credit.financing_ready_score,
                "建议融资档位": credit.financing_level,
            }
        ]
    )
    st.dataframe(credit_df, use_container_width=True, hide_index=True)
    st.caption("需补充沉淀的数据：" + "、".join(credit.recommended_data))
    st.caption(credit.recommendation)

    st.subheader("供应商 / 客户尽调")
    osint_df = pd.DataFrame(
        [
            {
                "对象": check.subject,
                "检查项": check.item,
                "状态": {"pass": "通过", "attention": "关注", "pending": "待确认"}[check.status],
                "说明": check.note,
            }
            for check in osint.checks
        ]
    )
    st.dataframe(osint_df, use_container_width=True, hide_index=True)
    st.caption(osint.recommendation)

    st.subheader("多脑冲突裁决（置信度 × 权重）")
    c1, c2, c3 = st.columns(3)
    c1.metric("冲突等级", {"high": "高", "medium": "中", "low": "低"}[conflict.conflict_level])
    c2.metric("裁决后得分", f"{conflict.adjusted_score:.1f} / 100")
    c3.metric("得分变化", f"{conflict.score_change:+.1f}")
    conflict_df = pd.DataFrame(
        [
            {
                "信号": signal.name,
                "评分": signal.score,
                "置信度": f"{signal.confidence:.0%}",
                "权重": f"{signal.weight:.0%}",
                "来源": signal.source,
            }
            for signal in conflict.signals
        ]
    )
    st.dataframe(conflict_df, use_container_width=True, hide_index=True)
    st.caption(conflict.decision)
    if conflict.reasons:
        st.caption("；".join(conflict.reasons))

    st.subheader("物流三方案对比")
    logistics_results = calculator.compare_logistics(
        LandedCostInput(
            category=category,
            market=market,
            unit_price_usd=unit_price,
            procurement_cost_cny=procurement_cny,
            payment_code=payment_code,
            tariff_rate=alert.effective_tariff_rate,
            min_duty_usd=alert.min_duty_usd,
        )
    )
    if logistics_results:
        st.session_state["trade_summary"]["best_logistics"] = logistics_results[0].logistics.name
    logistics_df = pd.DataFrame(
        [
            {
                "物流方案": r.logistics.name,
                "时效（天）": r.logistics.delivery_days,
                "单件物流（美元）": r.logistics_cost_usd,
                "到岸总成本（美元）": r.landed_cost_usd,
                "利润率%": r.margin_pct,
                "说明": r.logistics.note,
            }
            for r in logistics_results
        ]
    )
    st.dataframe(logistics_df, use_container_width=True, hide_index=True)

    st.subheader("合规与市场准入清单")
    req_df = pd.DataFrame(
        [
            {
                "要求": r.item,
                "成本（美元）": r.cost_usd,
                "周期（天）": r.duration_days,
                "来源": r.source,
                "是否必选": "是" if r.required else "可选",
                "说明": r.note,
            }
            for r in compliance.requirements
        ]
    )
    st.dataframe(req_df, use_container_width=True, hide_index=True)
    st.caption(compliance.recommendation)

    st.subheader("卖前体检清单")
    preflight_df = pd.DataFrame(
        [
            {
                "分组": item.group,
                "检查项": item.item,
                "状态": {"pass": "通过", "attention": "关注", "pending": "待确认"}[item.status],
                "说明": item.note,
            }
            for item in preflight.items
        ]
    )
    st.dataframe(preflight_df, use_container_width=True, hide_index=True)
    st.caption(preflight.recommendation)

    st.subheader("知识产权风险筛查（USPTO / EUIPO 演示库）")
    p1, p2 = st.columns(2)
    p1.metric("IP 风险", {"high": "高", "medium": "中", "low": "低"}[ip_result.risk_level])
    p2.metric("风险评分", f"{ip_result.risk_score:.0f} / 100")
    if ip_result.matched_records:
        ip_df = pd.DataFrame(
            [
                {
                    "标记 / 专利名称": record.mark,
                    "类型": record.kind,
                    "权利人": record.holder,
                    "来源": record.source,
                    "风险": {"high": "高", "medium": "中", "low": "低"}[record.risk],
                    "说明": record.note,
                }
                for record in ip_result.matched_records
            ]
        )
        st.dataframe(ip_df, use_container_width=True, hide_index=True)
    else:
        st.info("演示库未命中记录，仍需结合官方商标 / 专利库做最终核验。")
    st.caption(ip_result.recommendation)


_PAGE_OPTIONS = [
    "概览",
    "多源热度趋势",
    "未来90天预测",
    "选品推荐",
    "组合对比",
    "市场对比",
    "贸易决策",
    "数据分析",
    "数据体检",
    "联网搜索",
]

def _ai_settings() -> dict:
    """读取全局 AI 接入配置（主 Demo 顶部统一填写，同步到后端内存 / .env）。"""
    from src.api import ai_config

    status = ai_config.get_status()
    return {
        "api_key": ai_config.get_api_key() or os.environ.get("OPENAI_API_KEY", ""),
        "base_url": status.get("base_url") or os.environ.get("OPENAI_BASE_URL", ""),
        "model": status.get("model") or os.environ.get("OPENAI_MODEL", ""),
        "timeout": int(status.get("timeout") or 45),
    }


def _init_state(history=None) -> None:
    defaults = {
        "category": next(iter(CATEGORIES)),
        "market": "us",
        "model": "lightgbm_advanced",
        "active_page": "概览",
        "top_n": 10,
    }
    if history is not None and not history.empty:
        defaults["category"] = history["category"].iloc[0]
        defaults["market"] = history["market"].iloc[0]
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _apply_query_params() -> None:
    params = st.query_params
    for key in (
        "category",
        "market",
        "model",
        "top_n",
        "active_page",
    ):
        if key not in params:
            continue
        value = params[key]
        if key == "active_page" and value not in _PAGE_OPTIONS:
            continue
        if key == "top_n":
            try:
                value = int(value)
            except (TypeError, ValueError):
                continue
        st.session_state[key] = value


def _filter_history(history, category, market, date_from, date_to):
    sub = history[(history["category"] == category) & (history["market"] == market)]
    if date_from is not None:
        sub = sub[sub["date"].dt.date >= date_from]
    if date_to is not None:
        sub = sub[sub["date"].dt.date <= date_to]
    return sub


@st.cache_data(show_spinner=False)
def _combo_trade_metrics(history, category, market) -> dict:
    sub = history[(history["category"] == category) & (history["market"] == market)]
    price = float(sub.sort_values("date").iloc[-1]["price_median"]) if not sub.empty else 30.0
    decision = build_trade_decision(
        category=category,
        market=market,
        unit_price_usd=price,
        procurement_cost_cny=round(price * 7.15 * 0.35, 2),
    )
    return {
        "margin_pct": decision["margin_pct"],
        "feasibility_score": decision["feasibility_score"],
        "risk_level": decision["risk_level"],
        "hs_code": decision["hs_code"],
        "preflight_ready": decision["preflight"]["ready"],
    }


def _render_recommendation_page(recommendations) -> None:
    if recommendations.empty:
        st.info("暂无推荐数据。运行 `scripts\\run_pipeline.py` 后即可查看。")
        return
    eligible = (
        recommendations[recommendations["verdict"] != "No-Go"]
        if "verdict" in recommendations.columns
        else recommendations
    )
    if eligible.empty:
        eligible = recommendations
    max_n = min(20, len(eligible))
    top_n = st.slider("Top N", min_value=5, max_value=max_n, value=min(10, max_n), key="top_n")
    display = eligible.sort_values("rank").head(top_n).copy()
    display["品类"] = display["category"].map(category_name)
    display["市场"] = display["market"].map(market_name)
    display["综合评分"] = display["score"]
    display["六维评分"] = display["six_dimension_score"]
    display["判定"] = display["verdict"]
    display["预测增长%"] = display["forecast_growth"]
    display["搜索趋势%"] = display["search_trend"]
    display["竞争度"] = display["competition"]
    display["推荐理由"] = display["reasons"]
    st.dataframe(
        display[
            [
                "rank",
                "品类",
                "市场",
                "综合评分",
                "六维评分",
                "判定",
                "预测增长%",
                "搜索趋势%",
                "竞争度",
                "推荐理由",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )
    chart_df = display.sort_values("score")
    fig = px.bar(
        chart_df,
        x="score",
        y=chart_df["品类"] + " × " + chart_df["市场"],
        orientation="h",
        title="Top N 选品推荐综合评分",
        color="score",
        color_continuous_scale=["#101826", "#0E7490", "#22D3EE", "#67E8F9"],
        text=chart_df["score"].round(1),
    )
    fig.update_traces(texttemplate="%{text:.1f} 分", textposition="outside", cliponaxis=False)
    fig.update_traces(hovertemplate="<b>%{y}</b>：%{x:.1f} 分<extra></extra>")
    _chart_layout(fig, "Top N 选品推荐综合评分", x_title="综合评分（0-100）", y_title="组合", height=460)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("进入贸易测算")
    options = [
        f"{row['rank']}. {category_name(row['category'])} × {market_name(row['market'])}（{row['score']:.1f} 分）"
        for _, row in display.iterrows()
    ]
    selected = st.selectbox("选择候选组合", options=options, key="reco_select")
    if st.button("进入贸易测算", type="primary", key="reco_goto"):
        idx = options.index(selected)
        row = display.iloc[idx]
        st.session_state["category"] = row["category"]
        st.session_state["market"] = row["market"]
        st.session_state["selected_recommendation"] = row.to_dict()
        st.session_state["active_page"] = "贸易决策"
        st.rerun()


def _render_compare(history, forecast, recommendations) -> None:
    st.subheader("组合对比")
    if not recommendations.empty:
        combos = sorted({(row["category"], row["market"]) for _, row in recommendations.iterrows()})
    else:
        combos = [(category, market) for category in CATEGORIES for market in MARKETS]
    label_map = {f"{category_name(c)} × {market_name(m)}": (c, m) for c, m in combos}
    selected_labels = st.multiselect(
        "选择 2-4 个组合",
        options=list(label_map),
        default=list(label_map)[:2],
        key="compare_select",
    )
    if len(selected_labels) < 2:
        st.info("请至少选择 2 个组合进行对比。")
        return
    selected = [label_map[label] for label in selected_labels[:4]]
    metric_cols = [
        "综合评分",
        "六维评分",
        "预测增长",
        "搜索趋势",
        "低竞争度",
        "评价增长",
        "到岸利润",
        "准入评分",
    ]
    rows = []
    for category, market in selected:
        rec_rows = recommendations[
            (recommendations["category"] == category) & (recommendations["market"] == market)
        ]
        rec = rec_rows.sort_values("score", ascending=False).iloc[0] if not rec_rows.empty else None
        trade = _combo_trade_metrics(history, category, market)
        rows.append(
            {
                "组合": f"{category_name(category)} × {market_name(market)}",
                "综合评分": float(rec["score"]) if rec is not None else None,
                "六维评分": float(rec["six_dimension_score"]) if rec is not None else None,
                "预测增长": float(rec["forecast_growth"]) if rec is not None else None,
                "搜索趋势": float(rec["search_trend"]) if rec is not None else None,
                "低竞争度": 100 - float(rec["competition"]) if rec is not None else None,
                "评价增长": float(rec["review_growth"]) if rec is not None else None,
                "到岸利润": trade.get("margin_pct"),
                "准入评分": trade.get("feasibility_score"),
            }
        )
    compare_df = pd.DataFrame(rows)
    radar_df = compare_df.copy()
    for col in metric_cols:
        radar_df[col] = _normalize(pd.to_numeric(radar_df[col], errors="coerce"))
    fig = go.Figure()
    for _, row in radar_df.iterrows():
        values = [row[col] for col in metric_cols]
        fig.add_trace(
            go.Scatterpolar(
                r=values + values[:1],
                theta=metric_cols + metric_cols[:1],
                fill="toself",
                name=row["组合"],
                hovertemplate="<b>%{theta}</b>：%{r:.1f}（归一化 0-100）<extra>%{fullData.name}</extra>",
            )
        )
    _chart_layout(
        fig,
        "组合能力雷达（归一化 0-100）",
        height=480,
        hovermode="closest",
        margin=dict(l=40, r=40, t=60, b=20),
        polar=dict(radialaxis=dict(visible=True, range=[0, 100], title="归一化 0-100")),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(compare_df, use_container_width=True, hide_index=True)


def _build_export_payload(history) -> dict:
    category = st.session_state.get("category")
    market = st.session_state.get("market")
    model = st.session_state.get("model")
    date_range = st.session_state.get("date_range")
    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        date_from, date_to = date_range
    else:
        date_from = date_to = None
    trade_summary = st.session_state.get("trade_summary") or {}
    if not trade_summary:
        try:
            trade_summary = _combo_trade_metrics(history, category, market)
        except Exception:  # noqa: BLE001 - 无数据时导出仍可使用空摘要
            trade_summary = {}
    return {
        "filters": {
            "category": category,
            "market": market,
            "model": model,
            "date_from": str(date_from) if date_from else None,
            "date_to": str(date_to) if date_to else None,
            "top": st.session_state.get("top_n"),
        },
        "recommendation": st.session_state.get("selected_recommendation") or {},
        "trade_decision": trade_summary,
        "evidence": st.session_state.get("evidence", []),
        "conclusion": st.session_state.get("search_conclusion", ""),
        "data_status": _daily_status(),
    }


def _render_eda_tab() -> None:
    from src.analysis.eda import build_eda_report

    uploaded = st.file_uploader("上传数据文件", type=["csv", "json"])
    if uploaded is None:
        return
    try:
        if uploaded.name.lower().endswith(".csv"):
            df = pd.read_csv(uploaded)
        else:
            data = json.loads(uploaded.getvalue().decode("utf-8"))
            records = (
                data
                if isinstance(data, list)
                else data.get("rows") or data.get("history") or []
            )
            df = pd.DataFrame(records)
    except Exception as exc:  # noqa: BLE001 - 上传解析失败直接提示
        st.error(f"解析失败：{exc}")
        return
    with st.spinner("生成数据体检报告 ..."):
        report = build_eda_report(df)
    st.json(
        {
            "summary": report["summary"],
            "ab_tests": report["ab_tests"],
        }
    )
    st.metric("异常行", len(report["anomalies"]))
    if report.get("html_report"):
        st.download_button(
            "下载报告",
            data=open(report["html_report"], "rb").read(),
            file_name=os.path.basename(report["html_report"]),
            mime="text/html",
        )


def _export_report_button(history) -> None:
    def render_links(result: dict) -> None:
        md_b64 = base64.b64encode(result["markdown_path"].read_bytes()).decode("ascii")
        pdf_b64 = base64.b64encode(result["pdf_path"].read_bytes()).decode("ascii")
        st.markdown(
            '<div class="export-links">'
            '<a href="data:text/markdown;base64,' + md_b64 + '" download="dashboard_selection_report.md">下载 Markdown</a>'
            ' · '
            '<a href="data:application/pdf;base64,' + pdf_b64 + '" download="dashboard_selection_report.pdf">下载 PDF</a>'
            '</div>',
            unsafe_allow_html=True,
        )

    st.divider()
    st.subheader("一键导出决策报告")
    if st.button("生成 Markdown / PDF 报告", type="primary", key="export_report_btn"):
        try:
            result = build_selection_report(_build_export_payload(history))
            st.session_state["export_report_result"] = result
            st.success("报告已生成，可下载 Markdown 或 PDF。")
        except Exception as exc:  # noqa: BLE001 - 导出失败时展示给用户
            st.error(f"报告生成失败：{exc}")
    result = st.session_state.get("export_report_result")
    if result:
        render_links(result)


def _render_overview(
    history,
    forecast,
    recommendations,
    category,
    market,
    model,
    date_from,
    date_to,
) -> None:
    st.subheader("决策概览")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("覆盖品类", len(history["category"].unique()))
    c2.metric("覆盖市场", len(history["market"].unique()))
    c3.metric(
        "最新周销量均值",
        f"{history[history['date'] == history['date'].max()]['sales_volume'].mean():.1f}",
    )
    c4.metric("Top 推荐数", len(recommendations))

    st.subheader("综合结论")
    if recommendations.empty:
        st.info("暂无推荐数据，请先运行 `scripts\\run_pipeline.py` 生成推荐。")
    else:
        eligible = (
            recommendations[recommendations["verdict"] != "No-Go"]
            if "verdict" in recommendations.columns
            else recommendations
        )
        top_source = eligible if not eligible.empty else recommendations
        top = top_source.sort_values("rank").iloc[0]
        combo = f"{category_name(top['category'])} × {market_name(top['market'])}"
        st.success(
            f"当前最优组合为「{combo}」，综合评分 {top['score']:.1f}，"
            f"预测增长 {top['forecast_growth']:.1f}%，建议进入贸易测算核验成本与风险。"
        )

    n1, n2, n3 = st.columns(3)
    if n1.button("查看选品推荐", key="ov_go_reco"):
        st.session_state["active_page"] = "选品推荐"
        st.rerun()
    if n2.button("组合对比", key="ov_go_compare"):
        st.session_state["active_page"] = "组合对比"
        st.rerun()
    if n3.button("贸易测算", key="ov_go_trade"):
        st.session_state["active_page"] = "贸易决策"
        st.rerun()

    st.plotly_chart(
        _trend_chart(_filter_history(history, category, market, date_from, date_to), category, market),
        use_container_width=True,
    )
    _export_report_button(history)


def _inject_layout_css() -> None:
    st.markdown(
        """
<style>
.block-container{max-width:1400px;padding-top:1.6rem;padding-bottom:4rem}
[data-testid="stSidebar"]{min-width:300px;max-width:360px}
[data-testid="stMetric"]{padding:12px 14px}
[data-testid="stPlotlyChart"]{margin-top:14px}
@media (max-width:768px){
  [data-testid="stHorizontalBlock"]{flex-wrap:wrap}
  [data-testid="stHorizontalBlock"]>[data-testid="column"]{flex:1 1 100%!important;min-width:0}
  .block-container{padding-left:12px;padding-right:12px}
}
.st-logo-wrap{position:relative;width:150px;height:150px;margin:0 auto 6px;display:flex;align-items:center;justify-content:center;perspective:320px;transform-style:preserve-3d}
.st-logo-img{position:relative;z-index:2;width:124px;height:auto;max-height:100%;object-fit:contain;transform-style:preserve-3d;animation:st-logo-float 5.2s ease-in-out infinite;filter:drop-shadow(0 4px 10px rgba(2,8,18,.42)) drop-shadow(0 0 14px rgba(34,211,238,.3))}
.st-logo-ring{position:absolute;inset:-7px;z-index:1;border:1px solid transparent;border-top-color:rgba(125,211,252,.85);border-right-color:rgba(167,139,250,.5);border-radius:24px;pointer-events:none;animation:st-logo-ring-spin 7s linear infinite}
.st-logo-star{position:absolute;z-index:3;width:5px;height:5px;border-radius:50%;background:#fff;box-shadow:0 0 8px rgba(125,211,252,.95),0 0 16px rgba(167,139,250,.75);pointer-events:none;animation:st-logo-star-twinkle 2.8s ease-in-out infinite}
.st-ls-1{top:8%;left:12%}
.st-ls-2{top:20%;right:10%;animation-delay:.45s}
.st-ls-3{bottom:16%;left:18%;animation-delay:.9s}
.st-ls-4{bottom:10%;right:14%;animation-delay:1.35s}
.st-ls-5{top:48%;left:3%;animation-delay:1.8s}
.st-ls-6{top:54%;right:2%;animation-delay:2.25s}
.st-logo-sheen{position:absolute;inset:-14%;z-index:3;pointer-events:none;background:linear-gradient(115deg,transparent 28%,rgba(255,255,255,.24) 42%,rgba(125,211,252,.18) 50%,transparent 64%);background-size:220% 100%;mix-blend-mode:screen;animation:st-logo-sheen 4.8s linear infinite}
@keyframes st-logo-float{0%,100%{transform:translateZ(16px) rotateY(-9deg) rotateX(4deg) rotateZ(-2deg)}50%{transform:translateZ(34px) rotateY(11deg) rotateX(-3deg) rotateZ(2deg)}}
@keyframes st-logo-ring-spin{to{transform:rotate(360deg)}}
@keyframes st-logo-star-twinkle{0%,100%{opacity:.12;transform:scale(.6)}50%{opacity:1;transform:scale(1)}}
@keyframes st-logo-sheen{from{background-position:130% 0}to{background-position:-130% 0}}
</style>
""",
        unsafe_allow_html=True,
    )


def _render_animated_logo(logo_path: Path) -> None:
    encoded = base64.b64encode(logo_path.read_bytes()).decode("utf-8")
    st.markdown(
        f"""
<div class="st-logo-wrap">
  <span class="st-logo-ring" aria-hidden="true"></span>
  <img class="st-logo-img" src="data:image/jpeg;base64,{encoded}" alt="远帆智品">
  <span class="st-logo-star st-ls-1" aria-hidden="true"></span>
  <span class="st-logo-star st-ls-2" aria-hidden="true"></span>
  <span class="st-logo-star st-ls-3" aria-hidden="true"></span>
  <span class="st-logo-star st-ls-4" aria-hidden="true"></span>
  <span class="st-logo-star st-ls-5" aria-hidden="true"></span>
  <span class="st-logo-star st-ls-6" aria-hidden="true"></span>
  <span class="st-logo-sheen" aria-hidden="true"></span>
</div>
""",
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="跨境电商智能选品决策系统", page_icon="", layout="wide")
    _inject_layout_css()
    logo_path = Path(__file__).resolve().parent.parent.parent / "assets" / "logo.jpg"
    if logo_path.exists():
        _render_animated_logo(logo_path)
    st.title("跨境电商智能选品决策系统")
    st.caption("中国国际大学生创新大赛 · 高教赛道 · 创意组 ｜ AI + 数据分析")

    history = load_history()
    forecast = load_forecast()
    recommendations = load_recommendations()
    _init_state(history)
    _apply_query_params()
    _show_daily_status()

    if history.empty:
        st.warning("尚未生成清洗数据。请先运行 `scripts\\run_pipeline.py` 或 `scripts\\generate_demo_data.py`。")
        return

    with st.sidebar:
        st.header("筛选条件")
        st.selectbox("品类", options=list(CATEGORIES.keys()), format_func=category_name, key="category")
        st.selectbox("市场", options=list(MARKETS.keys()), format_func=market_name, key="market")
        model_options = ["prophet_baseline", "lightgbm_advanced"]
        if forecast.empty or not forecast["model"].isin(model_options).any():
            model_options = forecast["model"].unique().tolist() if not forecast.empty else model_options
        st.selectbox(
            "预测模型",
            options=model_options,
            format_func=lambda m: "Prophet 基线" if m == "prophet_baseline" else "LightGBM 进阶",
            key="model",
        )
        min_date = history["date"].min().date()
        max_date = history["date"].max().date()
        st.date_input(
            "日期范围",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            key="date_range",
        )
        st.divider()
        st.caption(f"数据覆盖：{WEEKS_HISTORY}周年粒度 · {len(CATEGORIES)}大品类 · {len(MARKETS)}大市场")
        if forecast.empty:
            st.warning("预测数据缺失，请运行 `scripts\\run_pipeline.py` 训练模型。")
        if recommendations.empty:
            st.warning("推荐数据缺失，请运行 `scripts\\run_pipeline.py` 生成推荐。")
        st.divider()
        ai_settings = _ai_settings()
        st.radio(
            "页面导航",
            options=_PAGE_OPTIONS,
            horizontal=True,
            key="active_page",
            label_visibility="collapsed",
        )

    category = st.session_state["category"]
    market = st.session_state["market"]
    model = st.session_state["model"]
    date_range = st.session_state.get("date_range") or (min_date, max_date)
    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        date_from, date_to = date_range
    else:
        date_from, date_to = min_date, max_date
    page = st.session_state["active_page"]

    if page == "概览":
        _render_overview(history, forecast, recommendations, category, market, model, date_from, date_to)
    elif page == "多源热度趋势":
        st.plotly_chart(
            _trend_chart(_filter_history(history, category, market, date_from, date_to), category, market),
            use_container_width=True,
        )
    elif page == "未来90天预测":
        if forecast.empty:
            st.info("暂无预测数据。运行 `scripts\\run_pipeline.py` 后即可查看。")
        else:
            st.plotly_chart(_forecast_chart(history, forecast, category, market, model), use_container_width=True)
    elif page == "选品推荐":
        _render_recommendation_page(recommendations)
    elif page == "组合对比":
        _render_compare(history, forecast, recommendations)
    elif page == "市场对比":
        st.plotly_chart(_market_compare(history), use_container_width=True)
    elif page == "贸易决策":
        _render_trade_tab(history, category, market)
        _export_report_button(history)
    elif page == "数据分析":
        _analysis_charts(history, forecast, recommendations)
    elif page == "数据体检":
        _render_eda_tab()
    elif page == "联网搜索":
        _search_panel(ai_settings)


if __name__ == "__main__":
    main()
