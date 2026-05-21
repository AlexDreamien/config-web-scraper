"""Declarative scraper configuration loaded from YAML.

A config describes three things:

1. **Where to fetch** — one of:
   - an explicit list of URLs;
   - a URL template with a page range (`url_template` + `pages.from / pages.to`);
   - a starting URL plus a CSS selector pointing at the "next page" link.

2. **What is an item** — `item_selector` picks one HTML node per record.
   If omitted, the page as a whole is treated as the single record.

3. **What to extract per item** — `fields` is a dict of field name to
   {selector, attr?}. With `attr`, that attribute is read; without it, the
   trimmed text content is used. A special attr `class` returns the full
   `class` attribute as a string.

A small `http` block tunes the user-agent, polite delay, retry count, and
timeout.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

__all__ = [
    "Config",
    "ConfigError",
    "FieldSpec",
    "HttpSettings",
    "PageRange",
    "Source",
    "load_config",
    "parse_config",
]


class ConfigError(ValueError):
    """Raised when a config file is missing or malformed."""


@dataclass(frozen=True)
class FieldSpec:
    selector: str
    attr: str | None = None


@dataclass(frozen=True)
class PageRange:
    from_: int
    to: int

    def __post_init__(self) -> None:
        if self.from_ < 1:
            raise ConfigError(f"pages.from must be >= 1, got {self.from_}")
        if self.to < self.from_:
            raise ConfigError(f"pages.to ({self.to}) must be >= pages.from ({self.from_})")

    def values(self) -> range:
        return range(self.from_, self.to + 1)


@dataclass(frozen=True)
class HttpSettings:
    user_agent: str = "config-web-scraper/0.1 (+https://github.com/AlexDreamien/config-web-scraper)"
    delay_seconds: float = 0.5
    retries: int = 3
    timeout_seconds: float = 10.0
    follow_redirects: bool = True


@dataclass(frozen=True)
class Source:
    urls: list[str] | None = None
    url_template: str | None = None
    pages: PageRange | None = None
    start_url: str | None = None
    next_page_selector: str | None = None
    max_pages: int | None = None

    def __post_init__(self) -> None:
        modes = sum(
            1
            for active in (
                self.urls is not None,
                self.url_template is not None and self.pages is not None,
                self.start_url is not None and self.next_page_selector is not None,
            )
            if active
        )
        if modes != 1:
            raise ConfigError(
                "source must define exactly one mode: 'urls', 'url_template + pages', "
                "or 'start_url + next_page_selector'"
            )
        if self.url_template is not None and "{page}" not in self.url_template:
            raise ConfigError("url_template must contain the {page} placeholder")
        if self.urls is not None and not self.urls:
            raise ConfigError("source.urls must not be empty")


@dataclass(frozen=True)
class Config:
    source: Source
    fields: dict[str, FieldSpec]
    item_selector: str | None = None
    http: HttpSettings = field(default_factory=HttpSettings)

    def __post_init__(self) -> None:
        if not self.fields:
            raise ConfigError("config must define at least one field in 'fields'")


def load_config(path: str | Path) -> Config:
    text = Path(path).read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML parse error: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError("top-level of config must be a mapping")
    return parse_config(data)


def parse_config(data: dict[str, Any]) -> Config:
    src_raw = _expect_mapping(data.get("source"), "source")
    pages_raw = src_raw.get("pages")
    pages = None
    if pages_raw is not None:
        pages = PageRange(
            from_=_expect_int(pages_raw.get("from"), "source.pages.from"),
            to=_expect_int(pages_raw.get("to"), "source.pages.to"),
        )

    source = Source(
        urls=_optional_str_list(src_raw.get("urls"), "source.urls"),
        url_template=_optional_str(src_raw.get("url_template"), "source.url_template"),
        pages=pages,
        start_url=_optional_str(src_raw.get("start_url"), "source.start_url"),
        next_page_selector=_optional_str(
            src_raw.get("next_page_selector"), "source.next_page_selector"
        ),
        max_pages=_optional_int(src_raw.get("max_pages"), "source.max_pages"),
    )

    fields_raw = _expect_mapping(data.get("fields"), "fields")
    fields = {}
    for name, value in fields_raw.items():
        if not isinstance(name, str) or not name:
            raise ConfigError(f"field name must be a non-empty string, got {name!r}")
        if isinstance(value, str):
            fields[name] = FieldSpec(selector=value)
        elif isinstance(value, dict):
            sel = value.get("selector")
            if not isinstance(sel, str) or not sel:
                raise ConfigError(f"fields.{name}.selector must be a non-empty string")
            attr = value.get("attr")
            if attr is not None and not isinstance(attr, str):
                raise ConfigError(f"fields.{name}.attr must be a string if set")
            fields[name] = FieldSpec(selector=sel, attr=attr)
        else:
            raise ConfigError(f"fields.{name} must be a string or mapping")

    item_selector = _optional_str(data.get("item_selector"), "item_selector")

    http_raw = data.get("http") or {}
    if not isinstance(http_raw, dict):
        raise ConfigError("http must be a mapping if set")
    http = HttpSettings(
        user_agent=http_raw.get(
            "user_agent", HttpSettings.__dataclass_fields__["user_agent"].default
        ),
        delay_seconds=float(http_raw.get("delay_seconds", 0.5)),
        retries=int(http_raw.get("retries", 3)),
        timeout_seconds=float(http_raw.get("timeout_seconds", 10.0)),
        follow_redirects=bool(http_raw.get("follow_redirects", True)),
    )

    return Config(source=source, fields=fields, item_selector=item_selector, http=http)


def _expect_mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{where} must be a mapping, got {type(value).__name__}")
    return value


def _expect_int(value: Any, where: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigError(f"{where} must be an integer, got {value!r}")
    return value


def _optional_int(value: Any, where: str) -> int | None:
    if value is None:
        return None
    return _expect_int(value, where)


def _optional_str(value: Any, where: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ConfigError(f"{where} must be a string, got {type(value).__name__}")
    return value


def _optional_str_list(value: Any, where: str) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise ConfigError(f"{where} must be a list of strings")
    for i, v in enumerate(value):
        if not isinstance(v, str):
            raise ConfigError(f"{where}[{i}] must be a string, got {type(v).__name__}")
    return list(value)
