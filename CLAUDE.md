# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Config-driven CLI scraper: describe extraction in YAML, get CSV/JSON. See `README.md` for the config schema and CLI.

## Build & test

```bash
pip install -r requirements.txt
python -m scraper.cli run examples/books_template.yaml -o books.csv
pip install -r requirements-dev.txt
pytest                              # offline via respx + stored HTML fixtures
pytest tests/test_parser.py::test_name   # single test
ruff check . && black --check .
```

## Architecture invariant

Each `scraper/` module has one responsibility (`config` / `fetcher` / `parser` / `pages` / `pipeline` / `exporter` / `cli`) and is reusable on its own. Keep parser/exporter usable on caller-supplied HTML; keep HTTP concerns in `fetcher`.

## Gotchas — do not regress

- **Follow-link pagination must guard against cycles.** `pipeline` tracks visited URLs and stops on a repeat. `max_pages` is optional (defaults to `None`), so it cannot be the only stop condition — a self-referential "next" link would otherwise loop forever.
- **YAML is loaded with `yaml.safe_load` only.** Never switch to `yaml.load` (arbitrary object construction).
- **Retry classification lives in `fetcher`:** 4xx fails fast *except* 429; 5xx / 429 / network errors retry with exponential backoff. Preserve this split.
- **`fetcher` uses an injected sleeper/clock** for deterministic tests — don't call `time.sleep` / `time.monotonic` directly in the request path.
- **CLI surfaces errors as messages, not tracebacks:** validation and `infer_format` failures go through `click.echo(..., err=True)` + `sys.exit`. Keep new error paths consistent.

## Out of scope (deliberate)

No JS rendering / headless browser, no proxy rotation, no GUI. Don't add these — point JS-dependent sites at Playwright instead.
