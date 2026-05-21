"""High-level orchestrator: config -> fetch -> parse -> export."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from scraper.config import Config
from scraper.exporter import ExportFormat, export
from scraper.fetcher import Fetcher, FetchError
from scraper.pages import static_urls
from scraper.parser import extract_items, find_next_page

__all__ = ["RunStats", "run"]

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunStats:
    pages_fetched: int
    pages_failed: int
    records: int


def run(config: Config, output_path: str | Path, fmt: ExportFormat) -> RunStats:
    field_names = list(config.fields.keys())
    records: list[dict[str, str | None]] = []
    pages_fetched = 0
    pages_failed = 0

    with Fetcher(config.http) as fetcher:
        urls = static_urls(config.source)
        if urls is not None:
            for url in urls:
                if _scrape_page(fetcher, url, config, records):
                    pages_fetched += 1
                else:
                    pages_failed += 1
        else:
            url = config.source.start_url
            assert url is not None
            sel = config.source.next_page_selector
            assert sel is not None
            visited = 0
            while url is not None:
                ok, html = _scrape_page_with_html(fetcher, url, config, records)
                if ok:
                    pages_fetched += 1
                else:
                    pages_failed += 1
                    break
                visited += 1
                if config.source.max_pages and visited >= config.source.max_pages:
                    break
                url = find_next_page(html, sel, url)

    export(records, output_path, fmt=fmt, field_names=field_names)
    log.info(
        "Done: %d pages fetched, %d failed, %d records written to %s",
        pages_fetched,
        pages_failed,
        len(records),
        output_path,
    )
    return RunStats(pages_fetched=pages_fetched, pages_failed=pages_failed, records=len(records))


def _scrape_page(
    fetcher: Fetcher,
    url: str,
    config: Config,
    records: list[dict[str, str | None]],
) -> bool:
    ok, _ = _scrape_page_with_html(fetcher, url, config, records)
    return ok


def _scrape_page_with_html(
    fetcher: Fetcher,
    url: str,
    config: Config,
    records: list[dict[str, str | None]],
) -> tuple[bool, str]:
    try:
        html = fetcher.fetch(url)
    except FetchError as exc:
        log.warning("Skipping %s: %s", url, exc)
        return False, ""
    page_records = extract_items(html, config.item_selector, config.fields)
    log.info("Page %s -> %d record(s)", url, len(page_records))
    records.extend(page_records)
    return True, html
