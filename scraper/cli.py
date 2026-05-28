"""click-based command-line interface."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from scraper.config import ConfigError, load_config
from scraper.exporter import infer_format
from scraper.pipeline import run as run_pipeline

__all__ = ["main"]


@click.group()
@click.option("-v", "--verbose", count=True, help="Increase logging verbosity (-v, -vv).")
def main(verbose: int) -> None:
    """Reusable, config-driven CLI web scraper."""
    level = logging.WARNING
    if verbose == 1:
        level = logging.INFO
    elif verbose >= 2:
        level = logging.DEBUG
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@main.command()
@click.argument("config_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "-o",
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    required=True,
    help="Output file path. Format is inferred from the extension (.csv or .json) "
    "unless --format is given.",
)
@click.option(
    "-f",
    "--format",
    "fmt",
    type=click.Choice(["csv", "json"]),
    default=None,
    help="Override the output format.",
)
def run(config_path: Path, output: Path, fmt: str | None) -> None:
    """Run the scraper described by CONFIG_PATH."""
    try:
        cfg = load_config(config_path)
    except ConfigError as exc:
        click.echo(f"Error: invalid config: {exc}", err=True)
        sys.exit(2)

    try:
        chosen_fmt = fmt or infer_format(output)
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(2)
    stats = run_pipeline(cfg, output, chosen_fmt)
    click.echo(
        f"Wrote {stats.records} record(s) from {stats.pages_fetched} page(s)"
        + (f", {stats.pages_failed} failed" if stats.pages_failed else "")
        + f" to {output}"
    )


if __name__ == "__main__":
    main()
