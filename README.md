# config-web-scraper

[![CI](https://github.com/AlexDreamien/config-web-scraper/actions/workflows/ci.yml/badge.svg)](https://github.com/AlexDreamien/config-web-scraper/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

A reusable, **config-driven** CLI scraper. Describe what to extract in YAML;
get CSV or JSON back. **No code changes per site** — same binary, new config.

> _Asciinema or terminal screenshot of a run lands here once captured._
>
> ![Run placeholder](docs/run.png)

## Features

- **Three pagination modes** (pick one per config):
  - explicit URL list,
  - URL template with a page range (`p-{page}.html` + `from: 1, to: 50`),
  - start URL plus a CSS selector pointing at the "next" link.
- **CSS-selector item + field extraction** via BeautifulSoup. Each field is
  text by default, or an attribute (including `class`) if `attr:` is set.
- **Polite, robust HTTP**: configurable User-Agent, inter-request delay,
  exponential backoff for 5xx / 429 / network errors, immediate fail on
  non-retryable 4xx.
- **CSV or JSON output**, format inferred from the output filename.
- **Failure tolerance**: a single broken page is logged and skipped; the
  end-of-run report shows how many succeeded vs. failed.

## Installation

```bash
git clone https://github.com/AlexDreamien/config-web-scraper.git
cd config-web-scraper
python -m venv .venv
.venv\Scripts\activate              # Windows
# source .venv/bin/activate         # macOS / Linux
pip install -r requirements.txt
```

## Quick start

```bash
python -m scraper.cli run examples/books_template.yaml -o books.csv
```

Sample output (first rows — see [`docs/sample_output.csv`](docs/sample_output.csv)):

```csv
title,url,price,availability,rating
A Light in the Attic,a-light-in-the-attic_1000/index.html,£51.77,In stock,star-rating Three
Tipping the Velvet,tipping-the-velvet_999/index.html,£53.74,In stock,star-rating One
Soumission,soumission_998/index.html,£50.10,In stock,star-rating One
```

> The `examples/` configs target [books.toscrape.com](https://books.toscrape.com)
> and [quotes.toscrape.com](https://quotes.toscrape.com) — public scraping
> sandboxes designed for learning. Use them as templates against your own
> target site.

## Config schema

```yaml
source:
  # Exactly one of three modes:
  urls:                # mode 1: explicit list
    - https://example.com/page1
    - https://example.com/page2
  # ---
  url_template: "https://example.com/p-{page}.html"  # mode 2: range
  pages:
    from: 1
    to: 5
  # ---
  start_url: "https://example.com/"                  # mode 3: follow links
  next_page_selector: "li.next > a"
  max_pages: 50                                       # optional safety cap

item_selector: "article.product"   # one item per matched node; omit to treat
                                   # the whole page as one record

fields:
  title:                           # mapping form
    selector: "h3 > a"
    attr: title                    # default is text; "class" joins with spaces
  price: "p.price_color"           # string shorthand = selector, text content

http:                              # all optional
  user_agent: "your-bot/1.0"
  delay_seconds: 0.5
  retries: 3
  timeout_seconds: 10
  follow_redirects: true
```

Every field is validated up front. Invalid configs fail fast with a path-style
message, e.g. `Error: invalid config: source.pages.to (3) must be >= pages.from (5)`.

## CLI

```
scraper run CONFIG_PATH -o OUTPUT [--format {csv,json}] [-v|-vv]
```

`-v` / `-vv` raise the log level to INFO / DEBUG.

## Architecture

```
scraper/
  config.py     Dataclass schema + YAML loader + validation
  fetcher.py    httpx wrapper: polite delay, exponential backoff,
                retry classification (4xx fail, 5xx/429/network retry)
  parser.py     extract_items() + find_next_page() over BeautifulSoup
  pages.py      static URL expansion (modes 1 & 2)
  pipeline.py   orchestrator: config -> fetcher -> parser -> exporter
  exporter.py   CSV and JSON writers
  cli.py        click entry point
tests/          61 unit + integration tests (config, fetcher, parser,
                exporter, pages, pipeline) — all offline via respx and
                stored HTML fixtures.
examples/       Working configs for books.toscrape.com and quotes.toscrape.com
```

Each module has a single responsibility so the pieces can be reused (e.g.
the parser and exporter work fine on HTML you supply yourself).

## Tests

```bash
pip install -r requirements-dev.txt
pytest
ruff check .
black --check .
```

61 tests covering:

- **config** — every source mode, mode conflicts, field shorthand vs.
  mapping, HTTP defaults / overrides, YAML/file errors
- **fetcher** — happy path, User-Agent, 4xx no-retry, 5xx / 429 retry,
  exhausted retries, network errors, deterministic delay book-keeping
  (via injected fake clock)
- **parser** — item-scoped extraction, text vs. attr vs. class,
  next-page URL resolution
- **exporter** — CSV column order from config, None → empty, JSON UTF-8
  passthrough, format inference
- **pages** — static URL expansion for both static modes
- **pipeline** — full integration via respx for all three source modes,
  partial-failure tolerance, max_pages clamping, field-order preservation

CI runs the same checks on every push (see `.github/workflows/ci.yml`).

## Out of scope

By design: no JavaScript rendering / headless browser, no proxy rotation,
no GUI. Sites that require JS are honestly out of scope — use Playwright or
similar for those.

## License

[MIT](LICENSE).
