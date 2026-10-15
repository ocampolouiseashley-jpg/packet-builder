"""Turn a CSV of records into one finished PDF packet per record."""

from __future__ import annotations

import csv
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .fill import fill_template, find_placeholders
from .pdf import assemble, merge

Converter = Callable[[Path, Path], Path]


@dataclass
class Options:
    template: Path
    data: Path
    out_dir: Path
    key_column: str
    attachments_dir: Path | None = None
    insert_after: int | None = None
    duplex: bool = False
    require_attachment: bool = True
    docx_only: bool = False


@dataclass
class RecordResult:
    key: str
    status: str  # "built" | "skipped"
    reasons: list[str] = field(default_factory=list)
    packet: Path | None = None
    pages: int = 0


@dataclass
class BuildResult:
    records: list[RecordResult]
    print_batch: Path | None = None
    report: Path | None = None

    @property
    def built(self) -> list[RecordResult]:
        return [r for r in self.records if r.status == "built"]

    @property
    def skipped(self) -> list[RecordResult]:
        return [r for r in self.records if r.status == "skipped"]


def safe_name(value: str) -> str:
    """A file-name-safe version of a record key."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("._")
    return cleaned or "record"


def read_records(data: Path) -> list[dict[str, str]]:
    with data.open(newline="", encoding="utf-8-sig") as fh:
        return [{k.strip(): (v or "").strip() for k, v in row.items() if k} for row in csv.DictReader(fh)]


def missing_fields(placeholders: set[str], row: dict[str, str]) -> list[str]:
    return sorted(name for name in placeholders if not row.get(name))


def find_attachment(attachments_dir: Path, key: str) -> Path | None:
    candidate = attachments_dir / f"{safe_name(key)}.pdf"
    return candidate if candidate.is_file() else None


def build(options: Options, convert: Converter) -> BuildResult:
    placeholders = find_placeholders(options.template)
    rows = read_records(options.data)
    if rows and options.key_column not in rows[0]:
        raise ValueError(f"Column '{options.key_column}' not found in {options.data.name}")

    docx_dir = options.out_dir / "docx"
    pdf_dir = options.out_dir / "pdf"
    packet_dir = options.out_dir / "packets"

    results: list[RecordResult] = []
    seen_keys: set[str] = set()

    for line_no, row in enumerate(rows, start=2):  # line 1 is the header
        key = row.get(options.key_column, "")
        result = RecordResult(key=key or f"(row {line_no})", status="skipped")
        results.append(result)

        if not key:
            result.reasons.append(f"Row {line_no}: no value in '{options.key_column}'")
            continue
        if safe_name(key) in seen_keys:
            result.reasons.append(f"Duplicate key '{key}' (row {line_no}); kept the first one")
            continue
        seen_keys.add(safe_name(key))

        if missing := missing_fields(placeholders, row):
            result.reasons.append("Missing values for: " + ", ".join(missing))

        attachment = None
        if options.attachments_dir is not None:
            attachment = find_attachment(options.attachments_dir, key)
            if attachment is None and options.require_attachment:
                result.reasons.append(f"No attachment {safe_name(key)}.pdf in {options.attachments_dir.name}/")

        if result.reasons:
            continue

        name = safe_name(key)
        filled = fill_template(options.template, row, docx_dir / f"{name}.docx")
        if options.docx_only:
            result.status, result.packet = "built", filled
            continue

        main_pdf = convert(filled, pdf_dir)
        packet = packet_dir / f"{name}.pdf"
        result.pages = assemble(
            main_pdf,
            packet,
            attachment=attachment,
            insert_after=options.insert_after,
            duplex=options.duplex,
        )
        result.status, result.packet = "built", packet

    batch = None
    packets = [r.packet for r in results if r.status == "built" and r.packet and r.packet.suffix == ".pdf"]
    if packets:
        batch = options.out_dir / "print_batch.pdf"
        merge(packets, batch)

    report = options.out_dir / "report.csv"
    options.out_dir.mkdir(parents=True, exist_ok=True)
    with report.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["key", "status", "pages", "file", "reasons"])
        for r in results:
            writer.writerow([r.key, r.status, r.pages or "", r.packet.name if r.packet else "", "; ".join(r.reasons)])

    return BuildResult(records=results, print_batch=batch, report=report)
