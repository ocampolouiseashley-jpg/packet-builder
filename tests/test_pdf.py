from pypdf import PdfReader

from packet_builder.pdf import assemble, merge


def labels(path):
    return [(page.extract_text() or "").strip() for page in PdfReader(str(path)).pages]


def test_attachment_goes_after_the_given_page(tmp_path, pdf_factory):
    main = pdf_factory("main.pdf", 3, "main")
    att = pdf_factory("att.pdf", 2, "att")
    out = tmp_path / "out.pdf"
    assert assemble(main, out, attachment=att, insert_after=2) == 5
    assert labels(out) == ["main 1", "main 2", "att 1", "att 2", "main 3"]


def test_attachment_defaults_to_the_end(tmp_path, pdf_factory):
    main = pdf_factory("main.pdf", 2, "main")
    att = pdf_factory("att.pdf", 1, "att")
    out = tmp_path / "out.pdf"
    assemble(main, out, attachment=att)
    assert labels(out) == ["main 1", "main 2", "att 1"]


def test_insert_after_past_the_end_appends(tmp_path, pdf_factory):
    main = pdf_factory("main.pdf", 2, "main")
    att = pdf_factory("att.pdf", 1, "att")
    out = tmp_path / "out.pdf"
    assemble(main, out, attachment=att, insert_after=12)
    assert labels(out) == ["main 1", "main 2", "att 1"]


def test_duplex_pads_every_odd_section(tmp_path, pdf_factory):
    main = pdf_factory("main.pdf", 3, "main")
    att = pdf_factory("att.pdf", 1, "att")
    out = tmp_path / "out.pdf"
    # sections: main 1 | att 1 | main 2-3  ->  1+blank, 1+blank, 2
    assert assemble(main, out, attachment=att, insert_after=1, duplex=True) == 6
    assert labels(out) == ["main 1", "", "att 1", "", "main 2", "main 3"]


def test_duplex_packet_always_has_even_pages(tmp_path, pdf_factory):
    for main_pages in range(1, 6):
        for att_pages in range(1, 4):
            main = pdf_factory(f"m{main_pages}.pdf", main_pages)
            att = pdf_factory(f"a{att_pages}.pdf", att_pages)
            total = assemble(main, tmp_path / "o.pdf", attachment=att, insert_after=2, duplex=True)
            assert total % 2 == 0


def test_merge_joins_packets(tmp_path, pdf_factory):
    a = pdf_factory("a.pdf", 2)
    b = pdf_factory("b.pdf", 3)
    assert merge([a, b], tmp_path / "batch.pdf") == 5
