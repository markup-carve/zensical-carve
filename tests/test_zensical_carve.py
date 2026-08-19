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
    assert "# Body {#Body}" in page
    # The front matter must not also appear in the body.
    assert "title: Lifted" in page.split("---\n", 2)[1]
    assert page.count("title: Lifted") == 1


def test_convert_tree_writes_a_sibling_page(tmp_path):
    docs = tmp_path / "docs"
    (docs / "guide").mkdir(parents=True)
    (docs / "guide" / "page.crv").write_text("# Page\n", encoding="utf-8")

    written = convert_tree(docs)

    assert written == [docs / "guide" / "page.md"]
    assert "# Page {#Page}" in written[0].read_text(encoding="utf-8")


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
    assert "# Two {#Two}" in (docs / "page.md").read_text(encoding="utf-8")


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


# --- theme adaptation ------------------------------------------------------
#
# These pin the four flaws a real build showed, each measured before the
# adapter existed: no table of contents, no permalinks, no code title or copy
# button, and a task list rendered with both a bullet and a checkbox.

from zensical_carve.theme import adapt  # noqa: E402


def test_headings_become_markdown_so_the_toc_can_see_them():
    out = adapt('<section id="Intro">\n  <h1>Intro</h1>\n  <p>x</p>\n</section>\n')
    assert "# Intro {#Intro}" in out
    assert "<h1>" not in out


def test_heading_keeps_its_own_id_and_classes():
    out = adapt('<section id="s"><h3 id="own" class="demo">T</h3></section>')
    assert "### T {#own .demo}" in out


def test_code_becomes_a_fence_with_the_title_the_theme_renders():
    out = adapt('<pre title="render.py"><code class="language-python">x = 1\n</code></pre>')
    assert '```python title="render.py"' in out
    assert "x = 1" in out
    assert "<pre" not in out


def test_code_fence_outgrows_a_backtick_run_in_the_payload():
    out = adapt("<pre><code>a ``` b</code></pre>")
    assert "````" in out


def test_code_entities_are_unescaped_back_to_source():
    out = adapt('<pre><code class="language-python">a &lt; b &amp;&amp; c</code></pre>')
    assert "a < b && c" in out


def test_html_chunks_are_left_aligned():
    """Carve indents by section depth, and a four-space indent is a code block."""
    out = adapt('<section id="a">\n  <h2>H</h2>\n    <p>deep</p>\n</section>\n')
    assert "\n<p>deep</p>" in out or out.startswith("<p>deep</p>")
    assert "\n    <p>deep</p>" not in out


def test_task_items_get_the_classes_the_theme_styles():
    out = adapt('<ul>\n  <li><input type="checkbox" checked disabled> a</li>\n</ul>')
    assert 'class="task-list"' in out
    assert 'class="task-list-item"' in out


def test_everything_else_survives_untouched():
    source = (
        '<aside class="admonition note"><p class="admonition-title">T</p></aside>\n'
        "<dl><dt>a</dt><dd>b</dd></dl>\n"
        "<table><caption>c</caption></table>\n"
        "<p><u>u</u> <mark>m</mark> <sub>2</sub></p>\n"
    )
    out = adapt(source)
    for fragment in ("admonition note", "<dl>", "<caption>c</caption>", "<u>u</u>", "<mark>m</mark>"):
        assert fragment in out


def test_convert_can_opt_out_of_theme_adaptation():
    page = convert("# H\n\nx\n", theme=False)
    assert "<h1>H</h1>" in page
    assert "# H {#" not in page
