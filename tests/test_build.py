import csv
from pathlib import Path

import pytest

from packet_builder.build import Options, build, safe_name
from tests.conftest import fake_converter

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def options(tmp_path, **overrides):
    data = dict(
        template=SAMPLES / "letter_template.docx",
        data=SAMPLES / "customers.csv",
        out_dir=tmp_path / "out",
        key_column="account_id",
        attachments_dir=SAMPLES / "attachments",
        insert_after=1,
        duplex=True,
    )
    data.update(overrides)
    return Options(**data)


def test_sample_batch(tmp_path):
    result = build(options(tmp_path), convert=fake_converter(pages=3))
    status = {r.key: r.status for r in result.records}
    assert status == {"ACC-1001": "built", "ACC-1002": "built", "ACC-1003": "skipped", "ACC-1004": "skipped"}

    reasons = {r.key: r.reasons for r in result.skipped}
    assert reasons["ACC-1003"] == ["Missing values for: contact_name"]
    assert "No attachment ACC-1004.pdf" in reasons["ACC-1004"][0]

    # letter p1 + blank | statement (1 page) + blank | letter p2-3  ->  6 pages each
    assert [r.pages for r in result.built] == [6, 6]
    assert result.print_batch is not None and result.print_batch.is_file()


def test_report_csv_lists_every_row(tmp_path):
    result = build(options(tmp_path), convert=fake_converter())
    with result.report.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert [r["key"] for r in rows] == ["ACC-1001", "ACC-1002", "ACC-1003", "ACC-1004"]


def test_optional_attachment_builds_without_it(tmp_path):
    result = build(options(tmp_path, require_attachment=False), convert=fake_converter())
    assert {r.key for r in result.built} == {"ACC-1001", "ACC-1002", "ACC-1004"}


def test_duplicate_keys_keep_the_first(tmp_path):
    with (SAMPLES / "customers.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    data = tmp_path / "dupes.csv"
    with data.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows([rows[0], rows[0]])
    result = build(options(tmp_path, data=data), convert=fake_converter())
    assert [r.status for r in result.records] == ["built", "skipped"]
    assert "Duplicate key" in result.records[1].reasons[0]


def test_wrong_key_column_is_a_clear_error(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        build(options(tmp_path, key_column="nope"), convert=fake_converter())


def test_docx_only_needs_no_converter(tmp_path):
    def must_not_run(*_):
        raise AssertionError("converter should not be called")

    result = build(options(tmp_path, docx_only=True), convert=must_not_run)
    assert all(r.packet.suffix == ".docx" for r in result.built)


@pytest.mark.parametrize("raw, expected", [("ACC-1001", "ACC-1001"), ("a/b c", "a_b_c"), ("  ", "record")])
def test_safe_name(raw, expected):
    assert safe_name(raw) == expected
