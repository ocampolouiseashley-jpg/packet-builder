"""PDF assembly: convert DOCX to PDF, insert attachments, pad for double-sided printing."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from pypdf import PdfReader, PdfWriter

SOFFICE_CANDIDATES = [
    "soffice",
    "libreoffice",
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
]


class ConversionError(Exception):
    pass


def find_soffice() -> str | None:
    for candidate in SOFFICE_CANDIDATES:
        found = shutil.which(candidate) or (candidate if Path(candidate).is_file() else None)
        if found:
            return found
    return None


def libreoffice_convert(docx_path: Path, out_dir: Path, timeout: int = 120) -> Path:
    """Convert one DOCX to PDF with LibreOffice running headless."""
    soffice = find_soffice()
    if not soffice:
        raise ConversionError("LibreOffice not found. Install it, or run with --docx-only.")
    out_dir.mkdir(parents=True, exist_ok=True)
    # A private profile directory lets several conversions run without
    # fighting over LibreOffice's user profile lock.
    with tempfile.TemporaryDirectory() as profile:
        result = subprocess.run(
            [
                soffice,
                f"-env:UserInstallation=file:///{Path(profile).as_posix().lstrip('/')}",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(out_dir),
                str(docx_path),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    pdf_path = out_dir / (docx_path.stem + ".pdf")
    if result.returncode != 0 or not pdf_path.is_file():
        raise ConversionError(f"LibreOffice could not convert {docx_path.name}: {result.stderr.strip()}")
    return pdf_path


def page_count(pdf_path: Path) -> int:
    return len(PdfReader(str(pdf_path)).pages)


def assemble(
    main_pdf: Path,
    out_path: Path,
    attachment: Path | None = None,
    insert_after: int | None = None,
    duplex: bool = False,
) -> int:
    """Build the final packet and return its page count.

    insert_after: put the attachment after this page of the main document
    (None = at the end). If the main document is shorter, the attachment goes
    at the end.
    duplex: add a blank page after the main section and after the attachment
    when they have an odd number of pages, so every section starts on the
    front of a sheet when printed double-sided.
    """
    main = PdfReader(str(main_pdf))
    writer = PdfWriter()

    main_pages = list(main.pages)
    split = len(main_pages) if insert_after is None else min(max(insert_after, 0), len(main_pages))

    def add_section(pages) -> None:
        for page in pages:
            writer.add_page(page)
        if duplex and len(pages) % 2 == 1:
            last = pages[-1]
            writer.add_blank_page(width=last.mediabox.width, height=last.mediabox.height)

    before, after = main_pages[:split], main_pages[split:]
    if attachment is None:
        add_section(main_pages)
    else:
        attached = list(PdfReader(str(attachment)).pages)
        if before:
            add_section(before)
        add_section(attached)
        if after:
            add_section(after)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as fh:
        writer.write(fh)
    return len(writer.pages)


def merge(pdfs: list[Path], out_path: Path) -> int:
    """Join packets into one print batch."""
    writer = PdfWriter()
    for pdf in pdfs:
        writer.append(str(pdf))
    with out_path.open("wb") as fh:
        writer.write(fh)
    return len(writer.pages)
