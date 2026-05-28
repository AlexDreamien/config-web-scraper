"""Tests for the CLI entry point."""

from __future__ import annotations

import json

import httpx
import respx
from click.testing import CliRunner

from scraper.cli import main

LISTING_HTML = """
<html><body>
  <article class="product">
    <h3><a href="/book-1" title="Book One">Book One</a></h3>
    <p class="price">$10.00</p>
  </article>
</body></html>
"""


def test_unknown_extension_prints_error_not_traceback(tmp_path):
    config_file = tmp_path / "cfg.yaml"
    config_file.write_text(
        "source:\n  urls:\n    - https://example.com/\n"
        "item_selector: article.product\n"
        "fields:\n  title: h3 > a\n",
        encoding="utf-8",
    )
    out = tmp_path / "out.xml"
    runner = CliRunner()
    result = runner.invoke(main, ["run", str(config_file), "-o", str(out)])
    assert result.exit_code == 2
    assert "Error:" in result.output
    assert "Traceback" not in result.output


@respx.mock
def test_successful_run_prints_summary(tmp_path):
    respx.get("https://example.com/").mock(return_value=httpx.Response(200, text=LISTING_HTML))
    config_file = tmp_path / "cfg.yaml"
    config_file.write_text(
        "source:\n  urls:\n    - https://example.com/\n"
        "item_selector: article.product\n"
        "fields:\n  title: h3 > a\n"
        "http:\n  delay_seconds: 0\n  retries: 0\n",
        encoding="utf-8",
    )
    out = tmp_path / "out.json"
    runner = CliRunner()
    result = runner.invoke(main, ["run", str(config_file), "-o", str(out)])
    assert result.exit_code == 0
    assert "1 record(s)" in result.output
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data[0]["title"] == "Book One"
