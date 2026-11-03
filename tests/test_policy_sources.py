"""Official-source policy adapter tests (mocked HTTP responses)."""

from __future__ import annotations

from datetime import date

from src.data import policy_sources


class FakeResponse:
    def __init__(self, payload=None, text="", status_code=200):
        self._payload = payload
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload or {}


def test_parse_official_event_marks_verified() -> None:
    event = policy_sources.parse_official_event(
        {
            "title": "US de minimis update",
            "link": "https://www.federalregister.gov/documents/example",
            "snippet": "The tariff rate increases by 25%.",
            "provider": "federal_register",
            "market": "us",
            "region": "foreign",
            "policy_type": "customs",
            "published_at": "2026-08-13",
        }
    )
    assert event["verified"] is True
    assert event["source_type"] == "official"
    assert event["official"] is True
    assert event["heuristic"] is False
    assert event["rate_ad_valorem"] == 0.25
    assert event["code"].startswith("pol-")


def test_federal_register_parser(monkeypatch) -> None:
    today = date.today().isoformat()
    response = FakeResponse(
        {
            "results": [
                {
                    "title": "Tariff on imports from China",
                    "publication_date": today,
                    "html_url": "https://www.federalregister.gov/documents/1",
                    "abstract": "A new tariff rule.",
                    "agencies": [{"name": "Office of the United States Trade Representative"}],
                    "type": {"label": "Rule"},
                    "document_number": "2026-00001",
                },
                {
                    "title": "Unrelated fishing notice",
                    "publication_date": today,
                    "html_url": "https://www.federalregister.gov/documents/2",
                    "abstract": "Fisheries management.",
                    "agencies": [{"name": "National Oceanic and Atmospheric Administration"}],
                    "type": {"label": "Notice"},
                    "document_number": "2026-00002",
                },
            ]
        }
    )
    monkeypatch.setattr(
        policy_sources.requests,
        "get",
        lambda *args, **kwargs: response,
    )
    items = policy_sources.fetch_federal_register(lookback_days=1)
    assert len(items) >= 1
    assert items[0]["provider"] == "federal_register"
    assert items[0]["market"] == "us"
    assert items[0]["link"].startswith("https://www.federalregister.gov")


def test_eu_press_corner_parser(monkeypatch) -> None:
    response = FakeResponse(
        {
            "docuLanguageListResources": [
                {
                    "title": "Customs tariff changes",
                    "eventDate": "2026-08-13",
                    "refCode": "IP/26/9999",
                    "docutype": {"code": "IP"},
                    "leadText": "New customs duties enter into force.",
                }
            ]
        }
    )
    monkeypatch.setattr(
        policy_sources.requests,
        "get",
        lambda *args, **kwargs: response,
    )
    monkeypatch.setattr(policy_sources, "_ec_taxation_news", lambda timeout: [])
    items = policy_sources.fetch_eu(lookback_days=1)
    assert len(items) == 1
    assert items[0]["provider"] == "eu"
    assert items[0]["link"].endswith("ip_26_9999")
    assert items[0]["market"] == "eu"


def test_gov_uk_parser(monkeypatch) -> None:
    today = date.today().isoformat()
    response = FakeResponse(
        {
            "results": [
                {
                    "title": "Tariff update for imports",
                    "link": "/government/news/tariff-update",
                    "description": "HMRC publishes the latest customs tariff.",
                    "public_timestamp": today + "T08:00:00Z",
                    "organisations": [{"title": "HM Revenue & Customs"}],
                    "content_store_document_type": "news_story",
                },
                {
                    "title": "Trade Tariff tool",
                    "link": "/trade-tariff",
                    "description": "Search commodity codes.",
                    "public_timestamp": "2025-01-01T00:00:00Z",
                    "organisations": [{"title": "HM Revenue & Customs"}],
                    "content_store_document_type": "transaction",
                },
            ]
        }
    )
    monkeypatch.setattr(
        policy_sources.requests,
        "get",
        lambda *args, **kwargs: response,
    )
    items = policy_sources.fetch_uk(lookback_days=1)
    assert len(items) == 1
    assert items[0]["provider"] == "uk"
    assert items[0]["link"].startswith("https://www.gov.uk")
    assert items[0]["market"] == "uk"


def test_collect_official_dedupes_and_reports_sources(monkeypatch) -> None:
    def same_item(name):
        return lambda **kwargs: [
            {
                "title": "Same official event",
                "link": "https://example.com/official/1",
                "snippet": "Customs duty update",
                "provider": name,
                "market": "us",
                "region": "foreign",
                "policy_type": "tariff",
                "published_at": date.today().isoformat(),
            }
        ]

    monkeypatch.setattr(
        policy_sources,
        "_FETCHERS",
        {
            "federal_register": same_item("federal_register"),
            "uk": same_item("uk"),
        },
    )
    payload = policy_sources.collect_official_policy_events(
        providers=("federal_register", "uk")
    )
    assert payload["count"] == 1
    assert payload["sources"]["federal_register"]["status"] == "ok"
    assert payload["sources"]["uk"]["status"] == "ok"
    assert payload["fallback_used"] is False


def test_collect_official_offline_never_fabricates() -> None:
    payload = policy_sources.collect_official_policy_events(offline=True)
    assert payload["events"] == []
    assert payload["fallback_used"] is True
    assert all(
        source["status"] == "offline"
        for source in payload["sources"].values()
    )
