"""Integration tests that mock HTTP and verify the whole pipeline."""

from __future__ import annotations

import csv
import json

import httpx
import respx

from scraper.config import parse_config
from scraper.pipeline import run

LISTING_HTML = """
<html><body>
  <article class="product">
    <h3><a href="/book-1" title="Book One">Book One</a></h3>
    <p class="price">$10.00</p>
  </article>
  <article class="product">
    <h3><a href="/book-2" title="Book Two">Book Two</a></h3>
    <p class="price">$12.00</p>
  </article>
  <a class="next" href="/page2">Next</a>
</body></html>
"""

LISTING_HTML_PAGE_2 = """
<html><body>
  <article class="product">
    <h3><a href="/book-3" title="Book Three">Book Three</a></h3>
    <p class="price">$14.00</p>
  </article>
</body></html>
"""


def _no_delay_config(source_block: dict, item_selector="article.product") -> dict:
    return {
        "source": source_block,
        "item_selector": item_selector,
        "fields": {
            "title": {"selector": "h3 > a", "attr": "title"},
            "price": "p.price",
        },
        "http": {"delay_seconds": 0, "retries": 0},
    }


@respx.mock
def test_explicit_urls_to_csv(tmp_path):
    respx.get("https://example.com/page1").mock(return_value=httpx.Response(200, text=LISTING_HTML))
    cfg = parse_config(_no_delay_config({"urls": ["https://example.com/page1"]}))
    out = tmp_path / "out.csv"
    stats = run(cfg, out, fmt="csv")
    assert stats.pages_fetched == 1
    assert stats.records == 2

    with open(out, encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["title", "price"]
    assert rows[1] == ["Book One", "$10.00"]
    assert rows[2] == ["Book Two", "$12.00"]


@respx.mock
def test_url_template_fetches_each_page(tmp_path):
    respx.get("https://example.com/p-1.html").mock(
        return_value=httpx.Response(200, text=LISTING_HTML)
    )
    respx.get("https://example.com/p-2.html").mock(
        return_value=httpx.Response(200, text=LISTING_HTML_PAGE_2)
    )
    cfg = parse_config(
        _no_delay_config(
            {
                "url_template": "https://example.com/p-{page}.html",
                "pages": {"from": 1, "to": 2},
            }
        )
    )
    out = tmp_path / "out.json"
    stats = run(cfg, out, fmt="json")
    assert stats.pages_fetched == 2
    assert stats.records == 3
    data = json.loads(out.read_text(encoding="utf-8"))
    assert [r["title"] for r in data] == ["Book One", "Book Two", "Book Three"]


@respx.mock
def test_follow_next_page_link(tmp_path):
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=LISTING_HTML))
    respx.get("https://example.com/page2").mock(
        return_value=httpx.Response(200, text=LISTING_HTML_PAGE_2)
    )
    cfg = parse_config(
        _no_delay_config(
            {
                "start_url": "https://example.com/",
                "next_page_selector": "a.next",
            }
        )
    )
    out = tmp_path / "out.json"
    stats = run(cfg, out, fmt="json")
    assert stats.pages_fetched == 2
    assert stats.records == 3


@respx.mock
def test_follow_link_stops_at_max_pages(tmp_path):
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=LISTING_HTML))
    # page2 should NOT be requested because max_pages=1.
    next_route = respx.get("https://example.com/page2").mock(
        return_value=httpx.Response(200, text=LISTING_HTML_PAGE_2)
    )
    block = _no_delay_config(
        {
            "start_url": "https://example.com/",
            "next_page_selector": "a.next",
            "max_pages": 1,
        }
    )
    cfg = parse_config(block)
    stats = run(cfg, tmp_path / "out.json", fmt="json")
    assert stats.pages_fetched == 1
    assert next_route.call_count == 0


@respx.mock
def test_one_failing_page_is_skipped_in_static_mode(tmp_path):
    respx.get("https://example.com/p-1.html").mock(
        return_value=httpx.Response(200, text=LISTING_HTML)
    )
    respx.get("https://example.com/p-2.html").mock(return_value=httpx.Response(500))
    cfg = parse_config(
        _no_delay_config(
            {
                "url_template": "https://example.com/p-{page}.html",
                "pages": {"from": 1, "to": 2},
            }
        )
    )
    stats = run(cfg, tmp_path / "out.json", fmt="json")
    assert stats.pages_fetched == 1
    assert stats.pages_failed == 1
    assert stats.records == 2  # only the records from the successful page


CYCLE_HTML = """
<html><body>
  <article class="product">
    <h3><a href="/book-1" title="Book One">Book One</a></h3>
    <p class="price">$10.00</p>
  </article>
  <a class="next" href="https://example.com/">Next</a>
</body></html>
"""


@respx.mock
def test_follow_link_stops_on_cycle(tmp_path):
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=CYCLE_HTML))
    cfg = parse_config(
        _no_delay_config(
            {
                "start_url": "https://example.com/",
                "next_page_selector": "a.next",
            }
        )
    )
    out = tmp_path / "out.json"
    stats = run(cfg, out, fmt="json")
    assert stats.pages_fetched == 1
    assert stats.records == 1


@respx.mock
def test_field_order_matches_config(tmp_path):
    respx.get("https://example.com/x").mock(return_value=httpx.Response(200, text=LISTING_HTML))
    cfg = parse_config(
        {
            "source": {"urls": ["https://example.com/x"]},
            "item_selector": "article.product",
            "fields": {
                "price": "p.price",
                "title": {"selector": "h3 > a", "attr": "title"},
            },
            "http": {"delay_seconds": 0, "retries": 0},
        }
    )
    out = tmp_path / "out.csv"
    run(cfg, out, fmt="csv")
    with open(out, encoding="utf-8") as f:
        header = next(csv.reader(f))
    assert header == ["price", "title"]
