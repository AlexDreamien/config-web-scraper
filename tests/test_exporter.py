from __future__ import annotations

import csv
import json

import pytest

from scraper.exporter import export, export_csv, export_json, infer_format

RECORDS = [
    {"title": "A Light in the Attic", "price": "£51.77", "rating": "Three"},
    {"title": "Tipping the Velvet", "price": "£53.74", "rating": "One"},
    {"title": "Soumission", "price": "£50.10", "rating": None},
]


class TestCSV:
    def test_header_and_rows(self, tmp_path):
        path = tmp_path / "out.csv"
        export_csv(RECORDS, path, field_names=["title", "price", "rating"])
        with open(path, encoding="utf-8") as f:
            rows = list(csv.reader(f))
        assert rows[0] == ["title", "price", "rating"]
        assert rows[1] == ["A Light in the Attic", "£51.77", "Three"]
        assert rows[3] == ["Soumission", "£50.10", ""]

    def test_field_name_order_preserved(self, tmp_path):
        path = tmp_path / "ordered.csv"
        export_csv(RECORDS, path, field_names=["rating", "title", "price"])
        with open(path, encoding="utf-8") as f:
            header = next(csv.reader(f))
        assert header == ["rating", "title", "price"]

    def test_missing_field_in_record_becomes_empty(self, tmp_path):
        path = tmp_path / "missing.csv"
        export_csv([{"title": "A"}], path, field_names=["title", "missing"])
        with open(path, encoding="utf-8") as f:
            rows = list(csv.reader(f))
        assert rows[1] == ["A", ""]


class TestJSON:
    def test_pretty_array(self, tmp_path):
        path = tmp_path / "out.json"
        export_json(RECORDS, path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data == RECORDS

    def test_unicode_is_not_escaped(self, tmp_path):
        path = tmp_path / "uni.json"
        export_json([{"price": "£51.77"}], path)
        text = path.read_text(encoding="utf-8")
        assert "£51.77" in text


class TestExportDispatch:
    def test_csv_via_export(self, tmp_path):
        path = tmp_path / "x.csv"
        n = export(RECORDS, path, fmt="csv", field_names=["title", "price"])
        assert n == 3
        with open(path, encoding="utf-8") as f:
            header = next(csv.reader(f))
        assert header == ["title", "price"]

    def test_json_via_export(self, tmp_path):
        path = tmp_path / "x.json"
        n = export(RECORDS, path, fmt="json")
        assert n == 3
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data == RECORDS

    def test_field_names_inferred_when_not_passed_for_csv(self, tmp_path):
        path = tmp_path / "inf.csv"
        export(RECORDS, path, fmt="csv")
        with open(path, encoding="utf-8") as f:
            header = next(csv.reader(f))
        assert header == ["title", "price", "rating"]

    def test_unknown_format(self, tmp_path):
        with pytest.raises(ValueError):
            export(RECORDS, tmp_path / "x.xml", fmt="xml")


class TestInferFormat:
    def test_csv(self):
        assert infer_format("out.csv") == "csv"

    def test_json(self):
        assert infer_format("OUT.JSON") == "json"

    def test_unknown(self):
        with pytest.raises(ValueError):
            infer_format("out.xml")
