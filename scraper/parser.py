"""Extract items and fields from HTML using CSS selectors."""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from scraper.config import FieldSpec

__all__ = ["extract_items", "find_next_page"]


def extract_items(
    html: str,
    item_selector: str | None,
    fields: dict[str, FieldSpec],
) -> list[dict[str, str | None]]:
    """Return one record per item node found via `item_selector`.

    If `item_selector` is None, the whole page is treated as a single
    item and one record is returned.

    Each field's selector is applied within the item's subtree, so
    selectors stay scoped (a global ``h1`` selector only matches an
    ``h1`` inside the item, not elsewhere on the page).

    A field whose selector finds nothing is ``None``. Otherwise its value
    is the trimmed text content, or — if `attr` is set — the attribute
    value (``class`` is joined with spaces; multi-valued attributes are
    stringified).
    """
    soup = BeautifulSoup(html, "lxml")
    if item_selector is None:
        return [{name: _extract_field(soup, spec) for name, spec in fields.items()}]
    items = soup.select(item_selector)
    return [{name: _extract_field(item, spec) for name, spec in fields.items()} for item in items]


def find_next_page(html: str, selector: str, base_url: str) -> str | None:
    """Resolve the ``href`` of the element matching `selector` against `base_url`.

    Returns None if the selector matches nothing or the matched element
    has no ``href``.
    """
    soup = BeautifulSoup(html, "lxml")
    el = soup.select_one(selector)
    if el is None:
        return None
    href = el.get("href")
    if not href:
        return None
    return urljoin(base_url, str(href))


def _extract_field(scope: Any, spec: FieldSpec) -> str | None:
    el = scope.select_one(spec.selector)
    if el is None:
        return None
    if spec.attr is None:
        return el.get_text(strip=True)
    value = el.get(spec.attr)
    if value is None:
        return None
    if isinstance(value, list):
        return " ".join(value)
    return str(value)
