"""Command line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .build import Options, build
from .pdf import ConversionError, libreoffice_convert


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="packet-builder",
        description="Fill a Word template for every row of a CSV and build print-ready PDF packets.",
    )
    parser.add_argument("--template", type=Path, required=True, help="Word template with {{placeholders}}")
    parser.add_argument("--data", type=Path, required=True, help="CSV file, one row per packet")
    parser.add_argument("--key", required=True, help="CSV column that identifies each record (used for file names)")
    parser.add_argument("--out", type=Path, default=Path("out"), help="Output folder (default: out)")
    parser.add_argument("--attachments", type=Path, help="Folder of PDFs named <key>.pdf to insert into each packet")
    parser.add_argument("--insert-after", type=int, help="Insert the attachment after this page (default: at the end)")
    parser.add_argument("--duplex", action="store_true", help="Pad sections to an even page count for double-sided printing")
    parser.add_argument("--optional-attachment", action="store_true", help="Build packets even when the attachment is missing")
    parser.add_argument("--docx-only", action="store_true", help="Only fill the Word files; skip PDF conversion")
    args = parser.parse_args(argv)

    for path in (args.template, args.data):
        if not path.is_file():
            parser.error(f"file not found: {path}")
    if args.attachments and not args.attachments.is_dir():
        parser.error(f"folder not found: {args.attachments}")

    options = Options(
        template=args.template,
        data=args.data,
        out_dir=args.out,
        key_column=args.key,
        attachments_dir=args.attachments,
        insert_after=args.insert_after,
        duplex=args.duplex,
        require_attachment=not args.optional_attachment,
        docx_only=args.docx_only,
    )

    try:
        result = build(options, convert=libreoffice_convert)
    except (ConversionError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    for r in result.records:
        line = f"{r.key}: {r.status.upper()}"
        if r.packet:
            line += f"  ->  {r.packet}" + (f"  ({r.pages} pages)" if r.pages else "")
        print(line)
        for reason in r.reasons:
            print(f"    - {reason}")

    print(f"\n{len(result.built)} built, {len(result.skipped)} skipped. Report: {result.report}")
    if result.print_batch:
        print(f"Print batch: {result.print_batch}")
    return 0 if not result.skipped else 1


if __name__ == "__main__":
    sys.exit(main())
