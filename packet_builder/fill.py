"""Fill {{placeholders}} in a Word template.

Word often splits text that looks like one word into several "runs" (for
example after a spell-check or a formatting change), so "{{client_name}}" can
be stored as "{{cli" + "ent_na" + "me}}". Replacing run by run misses those.
This module joins each paragraph's runs, replaces placeholders in the joined
text, and writes the result back into the first run, keeping that run's
formatting.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from docx import Document
from docx.document import Document as DocumentType
from docx.text.paragraph import Paragraph

PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")


def _paragraphs_in(container) -> Iterator[Paragraph]:
    yield from container.paragraphs
    for table in container.tables:
        for row in table.rows:
            for cell in row.cells:
                yield from _paragraphs_in(cell)


def all_paragraphs(doc: DocumentType) -> Iterator[Paragraph]:
    """Body, tables (including nested), headers and footers."""
    yield from _paragraphs_in(doc)
    for section in doc.sections:
        for part in (section.header, section.footer, section.first_page_header, section.first_page_footer):
            if part is not None and not part.is_linked_to_previous:
                yield from _paragraphs_in(part)


def find_placeholders(template: Path) -> set[str]:
    doc = Document(str(template))
    names: set[str] = set()
    for paragraph in all_paragraphs(doc):
        names.update(PLACEHOLDER.findall(paragraph.text))
    return names


def _fill_paragraph(paragraph: Paragraph, values: dict[str, str]) -> None:
    runs = paragraph.runs
    if not runs:
        return
    texts = [run.text for run in runs]
    original = list(texts)
    joined = "".join(texts)
    if "{{" not in joined:
        return

    # Start offset of each run inside the joined text.
    starts, pos = [], 0
    for text in texts:
        starts.append(pos)
        pos += len(text)

    def run_at(offset: int) -> int:
        for i in range(len(texts) - 1, -1, -1):
            if starts[i] <= offset and (original[i] or i == 0):
                return i
        return 0

    # Replace from the end so earlier offsets stay valid. Only the runs a
    # placeholder actually touches are edited; the value takes the formatting
    # of the run where the placeholder starts, and all other runs (bold
    # words, links, etc.) keep theirs.
    for match in reversed(list(PLACEHOLDER.finditer(joined))):
        name = match.group(1)
        if name not in values:
            continue
        first, last = run_at(match.start()), run_at(match.end() - 1)
        head = texts[first][: match.start() - starts[first]]
        tail = texts[last][match.end() - starts[last] :]
        if first == last:
            texts[first] = head + values[name] + tail
        else:
            texts[first] = head + values[name]
            for i in range(first + 1, last):
                texts[i] = ""
            texts[last] = tail

    for run, text in zip(runs, texts):
        if run.text != text:
            run.text = text


def fill_template(template: Path, values: dict[str, str], out_path: Path) -> Path:
    """Write a copy of `template` with every known placeholder replaced.

    Placeholders with no value are left as they are, so a missing field is
    visible in the output instead of silently becoming blank. Callers should
    check for missing fields before filling (see build.missing_fields).
    """
    doc = Document(str(template))
    for paragraph in all_paragraphs(doc):
        _fill_paragraph(paragraph, values)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
    return out_path
