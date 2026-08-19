"""Tests for zensical-carve.

The ones that matter here are not "does Carve render" - carve-lang has its own
suite for that. They are the three claims this package makes about ZENSICAL:
the fence signature is the one superfences calls, a generated page's front
matter parses to a dict so Zensical strips it, and the tree walker never
overwrites a page it did not write.
"""

from __future__ import annotations

import textwrap

import pytest
import yaml

from zensical_carve import CarveError, fence, render
from zensical_carve.preprocess import (
    GENERATED_MARKER,
    clean_tree,
    convert,
    convert_tree,
)


def test_render_produces_carve_html():
    html = render("A *bold* and /italic/ line.\n")
    assert "<strong>bold</strong>" in html
    assert "<em>italic</em>" in html


def test_render_uses_carve_emphasis_not_markdown():
    """The swap is the whole point: `*` is strong in Carve, emphasis in Markdown."""
    html = render("*strong* and _underline_\n")
    assert "<strong>strong</strong>" in html
    assert "<em>strong</em>" not in html


def test_fence_accepts_the_superfences_signature():
    """superfences calls with five positional arguments plus keywords."""
    html = fence("A *bold* line.\n", "carve", "carve", {}, None)
    assert "<strong>bold</strong>" in html


def test_fence_tolerates_extra_keywords():
    html = fence("x\n", "carve", "carve", {}, None, classes=[], id_value="", attrs={})
    assert "<p>x</p>" in html


def test_render_reports_a_refusal_as_carve_error():
    with pytest.raises(CarveError):
        render("x", extensions=["no-such-extension-exists"])


def test_generated_front_matter_parses_to_a_dict():
    """Zensical only strips front matter that parses to a dict.

    A block holding only a comment parses to None, is left in the body, and
    renders as a thematic break plus a heading. That is why the marker is a key.
    """
    page = convert("# Heading\n\nText.\n")
    assert page.startswith("---\n")
    body = page.split("---\n", 2)[1]
    meta = yaml.safe_load(body)
    assert isinstance(meta, dict)
    assert meta["zensical_carve"] == "generated"


def test_generated_page_lifts_the_carve_front_matter():
    source = textwrap.dedent(
        """\
        ---
        title: Lifted
        tags: [a, b]
        ---

        # Body

        Text.
        """
    )
    page = convert(source)
    meta = yaml.safe_load(page.split("---\n", 2)[1])
    assert meta["title"] == "Lifted"
    assert meta["tags"] == ["a", "b"]
    assert meta["zensical_carve"] == "generated"
    assert "<h1>Body</h1>" in page
    # The front matter must not also appear in the body.
    assert "title: Lifted" in page.split("---\n", 2)[1]
    assert page.count("title: Lifted") == 1


def test_convert_tree_writes_a_sibling_page(tmp_path):
    docs = tmp_path / "docs"
    (docs / "guide").mkdir(parents=True)
    (docs / "guide" / "page.crv").write_text("# Page\n", encoding="utf-8")

    written = convert_tree(docs)

    assert written == [docs / "guide" / "page.md"]
    assert "<h1>Page</h1>" in written[0].read_text(encoding="utf-8")


def test_convert_tree_refuses_to_clobber_a_hand_written_page(tmp_path, capsys):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.crv").write_text("# From Carve\n", encoding="utf-8")
    (docs / "page.md").write_text("# Hand written\n", encoding="utf-8")

    written = convert_tree(docs)

    assert written == []
    assert (docs / "page.md").read_text(encoding="utf-8") == "# Hand written\n"
    assert "skipping" in capsys.readouterr().err


def test_convert_tree_force_overwrites(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.crv").write_text("# From Carve\n", encoding="utf-8")
    (docs / "page.md").write_text("# Hand written\n", encoding="utf-8")

    written = convert_tree(docs, force=True)

    assert written == [docs / "page.md"]
    assert "From Carve" in (docs / "page.md").read_text(encoding="utf-8")


def test_convert_tree_updates_its_own_output(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.crv").write_text("# One\n", encoding="utf-8")
    convert_tree(docs)
    (docs / "page.crv").write_text("# Two\n", encoding="utf-8")

    written = convert_tree(docs)

    assert written == [docs / "page.md"]
    assert "<h1>Two</h1>" in (docs / "page.md").read_text(encoding="utf-8")


def test_clean_tree_removes_only_generated_pages(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "generated.crv").write_text("# Generated\n", encoding="utf-8")
    (docs / "kept.crv").write_text("# Kept\n", encoding="utf-8")
    convert_tree(docs)
    (docs / "kept.md").write_text("# Hand written\n", encoding="utf-8")

    removed = clean_tree(docs)

    assert removed == [docs / "generated.md"]
    assert (docs / "kept.md").exists()
    assert GENERATED_MARKER not in (docs / "kept.md").read_text(encoding="utf-8")
