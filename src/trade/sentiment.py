"""多语言舆情与本地化（离线演示版）。

内置英 / 西 / 德 / 日 / 葡情感词库与演示评论，按市场输出多语种情绪分、
正负面占比与趋势。真实场景可替换为评论抓取与多语种情感模型。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageSentiment:
    language: str
    language_name: str
    comment_count: int
    positive: int
    negative: int
    neutral: int
    score: float
    label: str
    trend: str
    sample_summary: str


@dataclass(frozen=True)
class SentimentResult:
    market: str
    languages: tuple[LanguageSentiment, ...]
    avg_score: float
    overall: str
    recommendation: str


LANGUAGE_META = {
    "en": {"name": "英语", "demo": "Great product and fast shipping, but packaging was poor."},
    "de": {"name": "德语", "demo": "Sehr gut und schnell, aber Verpackung war schlecht."},
    "es": {"name": "西班牙语", "demo": "Producto lento y embalaje malo, no es bueno."},
    "ja": {"name": "日语", "demo": "商品は最高で発送も早いが、梱包が悪い。"},
    "pt": {"name": "葡萄牙语", "demo": "Produto ótimo e rápido, mas embalagem ruim."},
    "ko": {"name": "韩语", "demo": "상품이 좋고 배송도 빠르지만 포장이 아쉽습니다."},
    "fr": {"name": "法语", "demo": "Produit excellent et rapide, mais emballage médiocre."},
    "vi": {"name": "越南语", "demo": "Sản phẩm tốt và giao nhanh, nhưng bao bì kém."},
    "ru": {"name": "俄语", "demo": "Товар отличный и быстрая доставка, но упаковка плохая."},
    "hu": {"name": "匈牙利语", "demo": "A termék kiváló és gyors a szállítás, de a csomagolás rossz."},
    "ar": {"name": "阿拉伯语", "demo": "المنتج ممتاز والشحن سريع لكن التغليف سيئ."},
}

# 演示口径：评论总数与正 / 负评论数，中性 = 总数 - 正 - 负
LANGUAGE_STATS = {
    "en": {"count": 120, "positive": 72, "negative": 18, "trend": "rising"},
    "de": {"count": 86, "positive": 41, "negative": 27, "trend": "flat"},
    "es": {"count": 64, "positive": 18, "negative": 32, "trend": "falling"},
    "ja": {"count": 40, "positive": 26, "negative": 6, "trend": "rising"},
    "pt": {"count": 35, "positive": 15, "negative": 12, "trend": "flat"},
    "ko": {"count": 45, "positive": 28, "negative": 5, "trend": "rising"},
    "fr": {"count": 70, "positive": 40, "negative": 18, "trend": "flat"},
    "vi": {"count": 55, "positive": 32, "negative": 13, "trend": "rising"},
    "ru": {"count": 48, "positive": 22, "negative": 17, "trend": "flat"},
    "hu": {"count": 30, "positive": 17, "negative": 6, "trend": "flat"},
    "ar": {"count": 52, "positive": 28, "negative": 12, "trend": "rising"},
}

MARKET_LANGUAGES = {
    "us": ("en",),
    "eu": ("de", "es", "pt"),
    "sea": ("en", "ja"),
    "jp": ("ja", "en"),
    "ca": ("en",),
    "au": ("en",),
    "uk": ("en",),
    "kr": ("ko",),
    "de": ("de",),
    "fr": ("fr",),
    "vn": ("vi",),
    "ru": ("ru",),
    "hu": ("hu",),
    "ae": ("ar",),
    "mx": ("es",),
}


class SentimentAnalyzer:
    """按目标市场聚合多语言舆情并输出情绪分与趋势。"""

    def analyze(self, market: str) -> SentimentResult:
        languages: list[LanguageSentiment] = []
        for code in MARKET_LANGUAGES[market]:
            meta = LANGUAGE_META[code]
            stats = LANGUAGE_STATS[code]
            neutral = stats["count"] - stats["positive"] - stats["negative"]
            score = round((stats["positive"] - stats["negative"]) / stats["count"], 3)
            if score > 0.15:
                label = "positive"
            elif score < -0.15:
                label = "negative"
            else:
                label = "neutral"
            languages.append(
                LanguageSentiment(
                    language=code,
                    language_name=meta["name"],
                    comment_count=stats["count"],
                    positive=stats["positive"],
                    negative=stats["negative"],
                    neutral=neutral,
                    score=score,
                    label=label,
                    trend=stats["trend"],
                    sample_summary=meta["demo"],
                )
            )

        avg_score = round(sum(item.score for item in languages) / len(languages), 3)
        if avg_score > 0.15:
            overall = "positive"
        elif avg_score < -0.15:
            overall = "negative"
        else:
            overall = "neutral"

        falling = [item.language_name for item in languages if item.trend == "falling"]
        negative = [item.language_name for item in languages if item.label == "negative"]
        if negative or falling:
            recommendation = (
                "存在负面或下滑语种（" + "、".join(negative or falling) + "），"
                "建议优先处理差评并调整本地化描述与售后话术。"
            )
        else:
            recommendation = "多语言舆情整体正面，可保持当前选品与本地化策略。"

        return SentimentResult(
            market=market,
            languages=tuple(languages),
            avg_score=avg_score,
            overall=overall,
            recommendation=recommendation,
        )
