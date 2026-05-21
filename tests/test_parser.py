from __future__ import annotations

from pathlib import Path

import pytest

from scraper.config import FieldSpec
from scraper.parser import extract_items, find_next_page

FIXTURE = Path(__file__).parent / "fixtures" / "books_listing.html"


@pytest.fixture(scope="module")
def html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


class TestExtractItems:
    def test_finds_all_items(self, html):
        records = extract_items(
            html,
            item_selector="article.product_pod",
            fields={"title": FieldSpec(selector="h3 > a", attr="title")},
        )
        assert [r["title"] for r in records] == [
            "A Light in the Attic",
            "Tipping the Velvet",
            "Soumission",
        ]

    def test_field_without_attr_returns_text(self, html):
        records = extract_items(
            html,
            item_selector="article.product_pod",
            fields={"price": FieldSpec(selector="p.price_color")},
        )
        assert records[0]["price"] == "£51.77"

    def test_attr_class_returns_joined_string(self, html):
        records = extract_items(
            html,
            item_selector="article.product_pod",
            fields={"rating": FieldSpec(selector="p.star-rating", attr="class")},
        )
        assert records[0]["rating"] == "star-rating Three"
        assert records[1]["rating"] == "star-rating One"

    def test_field_with_no_match_is_none(self, html):
        records = extract_items(
            html,
            item_selector="article.product_pod",
            fields={
                "title": FieldSpec(selector="h3 > a", attr="title"),
                "missing": FieldSpec(selector="div.does-not-exist"),
            },
        )
        assert records[0]["missing"] is None

    def test_multiple_fields(self, html):
        records = extract_items(
            html,
            item_selector="article.product_pod",
            fields={
                "title": FieldSpec(selector="h3 > a", attr="title"),
                "url": FieldSpec(selector="h3 > a", attr="href"),
                "price": FieldSpec(selector="p.price_color"),
                "availability": FieldSpec(selector="p.instock.availability"),
            },
        )
        assert records[0] == {
            "title": "A Light in the Attic",
            "url": "/catalogue/book-1/index.html",
            "price": "£51.77",
            "availability": "In stock",
        }

    def test_selectors_are_scoped_to_each_item(self, html):
        # Without item_selector + scoping, an `h3 > a` selector would only
        # ever pick the first match. Item-scoped extraction gives one per item.
        records = extract_items(
            html,
            item_selector="article.product_pod",
            fields={"title": FieldSpec(selector="h3 > a", attr="title")},
        )
        assert len(records) == 3

    def test_no_item_selector_treats_whole_page_as_one_item(self, html):
        records = extract_items(
            html,
            item_selector=None,
            fields={"first_title": FieldSpec(selector="article h3 > a", attr="title")},
        )
        assert records == [{"first_title": "A Light in the Attic"}]

    def test_no_items_match(self, html):
        records = extract_items(
            html,
            item_selector="article.does-not-exist",
            fields={"title": FieldSpec(selector="h3 > a", attr="title")},
        )
        assert records == []


class TestFindNextPage:
    def test_returns_resolved_url(self, html):
        url = find_next_page(html, "li.next > a", base_url="https://books.toscrape.com/catalogue/")
        assert url == "https://books.toscrape.com/catalogue/page-2.html"

    def test_returns_none_when_selector_misses(self, html):
        assert find_next_page(html, "li.does-not-exist > a", base_url="https://x.example") is None

    def test_returns_none_when_href_missing(self):
        html = "<html><body><a class='next'>next</a></body></html>"
        assert find_next_page(html, "a.next", base_url="https://x.example") is None
