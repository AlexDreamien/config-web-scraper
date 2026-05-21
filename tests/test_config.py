from __future__ import annotations

import pytest

from scraper.config import (
    ConfigError,
    FieldSpec,
    PageRange,
    load_config,
    parse_config,
)


def _minimal_fields() -> dict:
    return {"title": "h1"}


class TestSourceModes:
    def test_explicit_url_list(self):
        cfg = parse_config(
            {
                "source": {"urls": ["https://example.com/a", "https://example.com/b"]},
                "fields": _minimal_fields(),
            }
        )
        assert cfg.source.urls == ["https://example.com/a", "https://example.com/b"]

    def test_template_with_pages(self):
        cfg = parse_config(
            {
                "source": {
                    "url_template": "https://example.com/p-{page}.html",
                    "pages": {"from": 1, "to": 3},
                },
                "fields": _minimal_fields(),
            }
        )
        assert cfg.source.pages == PageRange(from_=1, to=3)
        assert list(cfg.source.pages.values()) == [1, 2, 3]

    def test_start_url_and_next_selector(self):
        cfg = parse_config(
            {
                "source": {
                    "start_url": "https://example.com",
                    "next_page_selector": "a.next",
                },
                "fields": _minimal_fields(),
            }
        )
        assert cfg.source.start_url == "https://example.com"
        assert cfg.source.next_page_selector == "a.next"

    def test_zero_modes_rejected(self):
        with pytest.raises(ConfigError, match="exactly one mode"):
            parse_config({"source": {}, "fields": _minimal_fields()})

    def test_two_modes_rejected(self):
        with pytest.raises(ConfigError, match="exactly one mode"):
            parse_config(
                {
                    "source": {
                        "urls": ["https://example.com"],
                        "start_url": "https://example.com",
                        "next_page_selector": "a.next",
                    },
                    "fields": _minimal_fields(),
                }
            )

    def test_url_template_requires_placeholder(self):
        with pytest.raises(ConfigError, match="placeholder"):
            parse_config(
                {
                    "source": {
                        "url_template": "https://example.com/no-placeholder",
                        "pages": {"from": 1, "to": 2},
                    },
                    "fields": _minimal_fields(),
                }
            )

    def test_empty_url_list_rejected(self):
        with pytest.raises(ConfigError, match="urls"):
            parse_config({"source": {"urls": []}, "fields": _minimal_fields()})


class TestPageRange:
    def test_from_must_be_positive(self):
        with pytest.raises(ConfigError):
            PageRange(from_=0, to=5)

    def test_to_must_be_at_least_from(self):
        with pytest.raises(ConfigError):
            PageRange(from_=5, to=3)


class TestFields:
    def test_string_shorthand_treated_as_selector(self):
        cfg = parse_config(
            {
                "source": {"urls": ["https://example.com"]},
                "fields": {"title": "h1.headline"},
            }
        )
        assert cfg.fields["title"] == FieldSpec(selector="h1.headline")

    def test_mapping_with_attr(self):
        cfg = parse_config(
            {
                "source": {"urls": ["https://example.com"]},
                "fields": {"href": {"selector": "a.next", "attr": "href"}},
            }
        )
        assert cfg.fields["href"] == FieldSpec(selector="a.next", attr="href")

    def test_at_least_one_field_required(self):
        with pytest.raises(ConfigError, match="at least one field"):
            parse_config({"source": {"urls": ["https://example.com"]}, "fields": {}})

    def test_invalid_field_value_rejected(self):
        with pytest.raises(ConfigError):
            parse_config(
                {
                    "source": {"urls": ["https://example.com"]},
                    "fields": {"title": 42},
                }
            )

    def test_missing_selector_in_mapping_rejected(self):
        with pytest.raises(ConfigError, match="selector"):
            parse_config(
                {
                    "source": {"urls": ["https://example.com"]},
                    "fields": {"title": {"attr": "href"}},
                }
            )


class TestHttpSettings:
    def test_defaults_when_block_omitted(self):
        cfg = parse_config(
            {
                "source": {"urls": ["https://example.com"]},
                "fields": _minimal_fields(),
            }
        )
        assert cfg.http.delay_seconds == 0.5
        assert cfg.http.retries == 3
        assert cfg.http.timeout_seconds == 10.0

    def test_overrides_respected(self):
        cfg = parse_config(
            {
                "source": {"urls": ["https://example.com"]},
                "fields": _minimal_fields(),
                "http": {
                    "user_agent": "custom-bot/1.0",
                    "delay_seconds": 1.5,
                    "retries": 5,
                    "timeout_seconds": 30,
                },
            }
        )
        assert cfg.http.user_agent == "custom-bot/1.0"
        assert cfg.http.delay_seconds == 1.5
        assert cfg.http.retries == 5
        assert cfg.http.timeout_seconds == 30.0


class TestLoad:
    def test_load_from_file(self, tmp_path):
        path = tmp_path / "config.yaml"
        path.write_text(
            "source:\n" "  urls: ['https://example.com']\n" "fields:\n" "  title: h1\n",
            encoding="utf-8",
        )
        cfg = load_config(path)
        assert cfg.source.urls == ["https://example.com"]
        assert cfg.fields["title"].selector == "h1"

    def test_invalid_yaml(self, tmp_path):
        path = tmp_path / "bad.yaml"
        path.write_text("source: [unclosed", encoding="utf-8")
        with pytest.raises(ConfigError, match="YAML parse error"):
            load_config(path)

    def test_non_mapping_top_level(self, tmp_path):
        path = tmp_path / "list.yaml"
        path.write_text("- a\n- b\n", encoding="utf-8")
        with pytest.raises(ConfigError, match="mapping"):
            load_config(path)
