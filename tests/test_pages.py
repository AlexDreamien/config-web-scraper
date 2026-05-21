from __future__ import annotations

from scraper.config import PageRange, Source
from scraper.pages import static_urls


def test_explicit_urls_returned_in_order():
    src = Source(urls=["https://a", "https://b", "https://c"])
    assert static_urls(src) == ["https://a", "https://b", "https://c"]


def test_template_expanded_for_each_page_in_range():
    src = Source(
        url_template="https://example.com/p-{page}.html",
        pages=PageRange(from_=2, to=4),
    )
    assert static_urls(src) == [
        "https://example.com/p-2.html",
        "https://example.com/p-3.html",
        "https://example.com/p-4.html",
    ]


def test_template_with_single_page_range():
    src = Source(
        url_template="https://example.com/p-{page}.html",
        pages=PageRange(from_=7, to=7),
    )
    assert static_urls(src) == ["https://example.com/p-7.html"]


def test_follow_link_mode_returns_none():
    src = Source(start_url="https://example.com", next_page_selector="a.next")
    assert static_urls(src) is None
