# packet-builder

Turns a spreadsheet into a stack of ready-to-mail document packets.

You give it a Word template with `{{placeholders}}`, a CSV with one row per recipient, and (optionally) a folder of PDFs to include with each letter. For every row it fills the template, converts it to PDF, inserts the attachment at the right page, adds blank pages so the packet prints correctly double-sided, and joins everything into one print batch. Rows with missing information are skipped and listed in a report instead of producing a letter with blanks in it.

Offices that send the same kind of letter to many people (collection notices, statements, legal notices, onboarding packs) do this by hand or with a mail merge plus a lot of manual PDF work. This tool does the whole run in one command.

```
$ packet-builder --template samples/letter_template.docx --data samples/customers.csv \
    --key account_id --attachments samples/attachments --insert-after 1 --duplex

ACC-1001: BUILT  ->  out/packets/ACC-1001.pdf  (4 pages)
ACC-1002: BUILT  ->  out/packets/ACC-1002.pdf  (4 pages)
ACC-1003: SKIPPED
    - Missing values for: contact_name
ACC-1004: SKIPPED
    - No attachment ACC-1004.pdf in attachments/

2 built, 2 skipped. Report: out/report.csv
Print batch: out/print_batch.pdf
```

All names, addresses and amounts in `samples/` are made up.

## What it handles

- **Placeholders Word has split up.** Word often stores `{{client_name}}` as several pieces ("runs") after an edit or spell-check, so a simple find-and-replace misses it. The filler works on the joined text of each paragraph and edits only the runs a placeholder touches, so bold words and other formatting elsewhere in the paragraph stay as they were. It covers body text, tables (including nested ones), headers and footers.
- **Missing data is caught before anything is generated.** Every placeholder in the template is checked against the row. A row with an empty field, no key, a duplicate key, or a missing attachment is skipped with the reason, and `out/report.csv` lists every row and what happened to it.
- **Attachments in the right place.** `--insert-after N` puts the attachment after page N of the letter; without it the attachment goes at the end. If the letter is shorter than N pages, the attachment is appended.
- **Double-sided printing.** With `--duplex`, each section (letter part, attachment, rest of the letter) is padded to an even number of pages, so every section starts on the front of a sheet and packets never share a sheet in the print batch.
- **Safe file names.** Keys like `a/b c` become `a_b_c`, so a value in the spreadsheet can't write outside the output folder.

## Run it

Requires Python 3.10+ and [LibreOffice](https://www.libreoffice.org/) for the Word-to-PDF step (it runs headless; nothing opens on screen).

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

packet-builder --template samples/letter_template.docx --data samples/customers.csv \
  --key account_id --attachments samples/attachments --insert-after 1 --duplex
```

No LibreOffice? `--docx-only` fills the Word files and still runs every check.

| Option | What it does |
|---|---|
| `--template` | Word template with `{{placeholders}}` |
| `--data` | CSV, one row per packet; column names match the placeholders |
| `--key` | Column that identifies each row; used for file names and to find the attachment (`<key>.pdf`) |
| `--attachments` | Folder of PDFs to insert |
| `--insert-after N` | Insert the attachment after page N (default: at the end) |
| `--duplex` | Pad sections for double-sided printing |
| `--optional-attachment` | Build the packet even when its attachment is missing |
| `--docx-only` | Only produce the filled Word files |
| `--out` | Output folder (default `out/`) |

The exit code is `0` when every row was built and `1` when any row was skipped.

To rebuild the sample files: `python scripts/make_samples.py`.

## Tests

```bash
pytest
```

20 tests cover split placeholders, formatting being kept, tables and headers, attachment placement, duplex padding (every combination of page counts comes out even), skipped rows, duplicate keys, the report, and safe file names. The Word-to-PDF step is swapped for a fake converter in the tests, so they run without LibreOffice.

## Layout

```
packet_builder/
  fill.py   Find and fill {{placeholders}} across runs, tables, headers, footers
  pdf.py    LibreOffice conversion, attachment insertion, duplex padding, merging
  build.py  Reads the CSV, validates each row, builds packets, writes the report
  cli.py    Command line interface
scripts/make_samples.py  Generates the fake template, CSV and attachments
tests/
```

## Possible next steps

- Address labels or envelope sheets in the same run.
- A small web page so non-technical staff can upload the template and CSV.
- Per-row rules (different attachment position for different document types).

Built with Claude Code as a coding assistant. I designed the behavior and the checks, and I review and test everything before it goes in.
