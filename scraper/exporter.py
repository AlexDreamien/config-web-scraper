"""Write scraped records to CSV or JSON."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

__all__ = ["ExportFormat", "export", "export_csv", "export_json", "infer_format"]

ExportFormat = str  # "csv" | "json"


def infer_format(path: str | Path) -> ExportFormat:
    suffix = Path(path).suffix.lower().lstrip(".")
    if suffix in {"csv", "json"}:
        return suffix
    raise ValueError(
        f"Cannot infer format from extension {suffix!r}; use --format or a .csv/.json filename"
    )


def export(
    records: Iterable[dict[str, Any]],
    path: str | Path,
    fmt: ExportFormat,
    field_names: list[str] | None = None,
) -> int:
    """Write records and return the count written."""
    materialised = list(records)
    if fmt == "csv":
        names = field_names or _infer_field_names(materialised)
        export_csv(materialised, path, names)
    elif fmt == "json":
        export_json(materialised, path)
    else:
        raise ValueError(f"Unknown format: {fmt!r}")
    return len(materialised)


def export_csv(
    records: Iterable[dict[str, Any]],
    path: str | Path,
    field_names: list[str],
) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=field_names, extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({name: _stringify(record.get(name)) for name in field_names})


def export_json(records: Iterable[dict[str, Any]], path: str | Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(list(records), f, indent=2, ensure_ascii=False)
        f.write("\n")


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _infer_field_names(records: list[dict[str, Any]]) -> list[str]:
    seen: dict[str, None] = {}
    for r in records:
        for k in r:
            seen.setdefault(k, None)
    return list(seen.keys())
