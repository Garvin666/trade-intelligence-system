"""Trafilatura-backed text extraction tests."""

from __future__ import annotations

import src.data.http as http_module


def _article_html() -> str:
    return """
    <html><head><title>Sample article</title></head><body>
      <script>function noise() { return 1; }</script>
      <article>
        <h1>Market trend</h1>
        <p>Body text here for the product signal.</p>
      </article>
    </body></html>
    """


def test_extract_main_text_uses_trafilatura() -> None:
    text = http_module.extract_main_text(_article_html())
    assert "Body text here" in text
    assert "Market trend" in text
    assert "function noise" not in text


def test_extract_main_text_falls_back_when_trafilatura_returns_none(
    monkeypatch,
) -> None:
    import trafilatura

    monkeypatch.setattr(
        trafilatura,
        "extract",
        lambda *args, **kwargs: None,
    )
    text = http_module.extract_main_text(_article_html())
    assert "Body text here" in text
    assert "function noise" not in text


def test_extract_main_text_empty() -> None:
    assert http_module.extract_main_text("") == ""
    assert http_module.extract_main_text("<p>  </p>").strip() == ""
