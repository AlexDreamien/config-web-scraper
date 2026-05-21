"""Pagination helpers.

Two of the three source modes (explicit URL list and templated page range)
yield a static, pre-computable URL sequence. The third mode (follow
``next_page_selector``) is necessarily driven by the orchestrator because
it needs the previous page's HTML to find the next URL.
"""

from __future__ import annotations

from scraper.config import Source

__all__ = ["static_urls"]


def static_urls(source: Source) -> list[str] | None:
    """Return all URLs for static modes, or None for follow-link mode."""
    if source.urls:
        return list(source.urls)
    if source.url_template and source.pages:
        return [
            source.url_template.replace("{page}", str(p)) for p in source.pages.values()
        ]
    return None
