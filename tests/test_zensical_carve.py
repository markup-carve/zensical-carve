"""Tests for zensical-carve.

The ones that matter here are not "does Carve render" - carve-lang has its own
suite for that. They are the three claims this package makes about ZENSICAL:
the fence signature is the one superfences calls, a generated page's front
matter parses to a dict so Zensical strips it, and the tree walker never
overwrites a page it did not write.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest
import yaml

from zensical_carve import CarveError, config, fence, render, symbols
from zensical_carve import preprocess
from zensical_carve.preprocess import (
    GENERATED_MARKER,
    SOURCE_KEY,
    clean_tree,
    convert,
    convert_tree,
    main,
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

    outcome = convert_tree(docs)

    assert outcome.written == [docs / "guide" / "page.md"]
    assert outcome.failed == []
    assert "# Page {#Page}" in outcome.written[0].read_text(encoding="utf-8")


def test_convert_tree_refuses_to_clobber_a_hand_written_page(tmp_path, capsys):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.crv").write_text("# From Carve\n", encoding="utf-8")
    (docs / "page.md").write_text("# Hand written\n", encoding="utf-8")

    outcome = convert_tree(docs)

    assert outcome.written == []
    assert outcome.skipped == [docs / "page.md"]
    assert (docs / "page.md").read_text(encoding="utf-8") == "# Hand written\n"
    assert "skipping" in capsys.readouterr().err


def test_convert_tree_force_overwrites(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.crv").write_text("# From Carve\n", encoding="utf-8")
    (docs / "page.md").write_text("# Hand written\n", encoding="utf-8")

    outcome = convert_tree(docs, force=True)

    assert outcome.written == [docs / "page.md"]
    assert "From Carve" in (docs / "page.md").read_text(encoding="utf-8")


def test_convert_tree_updates_its_own_output(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.crv").write_text("# One\n", encoding="utf-8")
    convert_tree(docs)
    (docs / "page.crv").write_text("# Two\n", encoding="utf-8")

    outcome = convert_tree(docs)

    assert outcome.written == [docs / "page.md"]
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


def test_a_code_block_holding_injected_markup_stays_html():
    """Code callouts put `<b class="callout">` inside the code block.

    Carve escapes a source `<` to `&lt;`, so a literal tag in the payload can
    only have been injected by an extension. Fencing it would print the tags.
    """
    out = adapt(
        '<pre><code class="language-rust">fn main() { '
        '<b class="callout" data-callout="1">1</b>\n}</code></pre>'
    )
    assert '<b class="callout"' in out
    assert "```rust" not in out


def test_an_ordinary_code_block_with_escaped_angle_brackets_still_fences():
    """`a &lt; b` is source, not markup, and must keep the theme's highlighting."""
    out = adapt('<pre><code class="language-c">if (a &lt; b) {}</code></pre>')
    assert "```c" in out
    assert "if (a < b) {}" in out


def test_a_deeply_indented_tag_is_left_aligned_even_when_the_chunk_starts_at_zero():
    """A four-space indent is a code block, and a common-prefix dedent misses it.

    The chunk opens at column 0 with a `<p>`, so there is no common prefix to
    strip - but the `<dl>` two sections deep would still render as a code block
    showing its own open tag.
    """
    out = adapt('<section id="a">\n<p>x</p>\n    <dl class="glossary">\n  <dt>t</dt>\n</dl>\n</section>')
    assert "\n<dl class=\"glossary\">" in out
    assert "    <dl" not in out


def test_whitespace_inside_pre_survives_the_dedent():
    """Indentation is insignificant between tags and significant inside <pre>."""
    out = adapt('<section id="a">\n  <pre><code>def f():\n    return 1\n</code></pre>\n</section>')
    assert "    return 1" in out


def test_whitespace_inside_textarea_survives_the_dedent():
    """A raw-text element keeps its whitespace, and a raw HTML block can hold one."""
    out = adapt('<section id="a">\n  <textarea>\n    value\n  </textarea>\n</section>')
    assert "\n    value" in out


# --- configuration ---------------------------------------------------------
#
# The table is read from the site's own configuration file. Zensical ignores a
# table it does not know - measured on 0.0.56, which builds a site whose
# zensical.toml carries [tool.zensical-carve] without a warning - so the
# settings can live next to the rest of the site's configuration.


def _write(path, text):
    path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")
    return path


def test_config_is_read_from_zensical_toml(tmp_path):
    _write(
        tmp_path / "zensical.toml",
        """
        [project]
        site_name = "Site"

        [tool.zensical-carve]
        extensions = ["details", "tabs"]
        emoji = "unicode"
        docs-dir = "pages"
        """,
    )

    settings = config.load(start=tmp_path)

    assert settings.extensions == ("details", "tabs")
    assert settings.emoji == "unicode"
    assert settings.docs_dir == Path("pages")
    assert settings.source == tmp_path / "zensical.toml"


def test_config_falls_back_to_pyproject(tmp_path):
    _write(tmp_path / "zensical.toml", '[project]\nsite_name = "Site"\n')
    _write(
        tmp_path / "pyproject.toml",
        """
        [tool.zensical-carve]
        extensions = ["details"]
        """,
    )

    settings = config.load(start=tmp_path)

    assert settings.extensions == ("details",)
    assert settings.source == tmp_path / "pyproject.toml"


def test_config_absent_is_the_default_not_an_error(tmp_path):
    settings = config.load(start=tmp_path)

    assert settings == config.Settings()
    assert settings.source is None


def test_config_rejects_an_unknown_key(tmp_path):
    _write(
        tmp_path / "zensical.toml",
        """
        [tool.zensical-carve]
        extenshuns = ["details"]
        """,
    )

    with pytest.raises(config.ConfigError) as error:
        config.load(start=tmp_path)

    assert "extenshuns" in str(error.value)
    assert "extensions" in str(error.value)


def test_config_rejects_a_wrong_type(tmp_path):
    _write(
        tmp_path / "zensical.toml",
        """
        [tool.zensical-carve]
        extensions = "details"
        """,
    )

    with pytest.raises(config.ConfigError):
        config.load(start=tmp_path)


def test_config_symbols_inline_and_from_a_file(tmp_path):
    (tmp_path / "symbols.json").write_text('{"crab": "\\ud83e\\udd80"}', encoding="utf-8")
    _write(
        tmp_path / "zensical.toml",
        """
        [tool.zensical-carve]
        symbols = "symbols.json"
        """,
    )
    assert config.load(start=tmp_path).symbols == {"crab": "🦀"}

    _write(
        tmp_path / "zensical.toml",
        """
        [tool.zensical-carve.symbols]
        crab = "🦀"
        """,
    )
    assert config.load(start=tmp_path).symbols == {"crab": "🦀"}


def test_merge_keeps_a_setting_a_flag_did_not_touch():
    """An unpassed store_true flag arrives as False and must not turn a key off."""
    settings = config.Settings(raw_html=True, extensions=("details",))

    merged = config.merge(settings, raw_html=False, extensions=None, emoji=None)

    assert merged.raw_html is True
    assert merged.extensions == ("details",)


def test_merge_lets_a_flag_win():
    settings = config.Settings(extensions=("details",))

    assert config.merge(settings, extensions=("tabs",)).extensions == ("tabs",)


# --- symbols ---------------------------------------------------------------


def test_symbol_map_renders_a_shortcode():
    symbol_map = symbols.emoji_map("unicode")
    if not symbol_map:  # pragma: no cover - zensical is an optional dependency
        pytest.skip("zensical is not installed, so there is no emoji index")

    assert symbol_map["smile"] == "😄"
    assert render("Hi :smile:\n", symbols=symbol_map).count("😄") == 1


def test_twemoji_mode_emits_the_element_zensical_emits():
    symbol_map = symbols.emoji_map("twemoji")
    if not symbol_map:  # pragma: no cover
        pytest.skip("zensical is not installed, so there is no emoji index")

    element = symbol_map["smile"]
    assert element.startswith('<img alt="😄" class="twemoji"')
    assert element.endswith('title=":smile:" />')
    # The engine substitutes a symbol RAW, which is what carries the element
    # through to the page instead of escaping it into visible text.
    assert element in render("Hi :smile:\n", symbols=symbol_map)


def test_symbol_map_is_empty_when_asked_for_nothing():
    assert symbols.emoji_map("none") == {}
    assert symbols.build("none") is None


def test_project_symbols_win_over_the_emoji_set():
    built = symbols.build("unicode", {"smile": "SMILE"})

    assert built is not None
    assert built["smile"] == "SMILE"


# --- diagnostics -----------------------------------------------------------


def test_a_failing_page_names_itself_and_the_others_are_still_written(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "good.crv").write_text("# Good\n", encoding="utf-8")
    (docs / "bad.crv").write_bytes(b"\xff\xfe not utf-8")

    outcome = convert_tree(docs)

    assert outcome.written == [docs / "good.md"]
    assert [path for path, _ in outcome.failed] == [docs / "bad.crv"]


def test_generated_page_records_its_source(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.crv").write_text("# Page\n", encoding="utf-8")

    convert_tree(docs)
    front_matter = yaml.safe_load(
        (docs / "page.md").read_text(encoding="utf-8").split("---")[1]
    )

    assert front_matter[SOURCE_KEY] == (docs / "page.crv").as_posix()


def test_cli_reports_a_failure_with_the_file_and_exits_one(tmp_path, capsys, monkeypatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.crv").write_text("# Page\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    code = main(["prepare", "--extension", "no-such-extension-exists"])

    assert code == 1
    assert "page.crv" in capsys.readouterr().err


def test_cli_reads_the_config_file(tmp_path, capsys, monkeypatch):
    _write(
        tmp_path / "zensical.toml",
        """
        [tool.zensical-carve]
        docs-dir = "pages"
        emoji = "unicode"
        """,
    )
    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / "page.crv").write_text("Hi :smile:\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert main(["prepare"]) == 0

    body = (pages / "page.md").read_text(encoding="utf-8")
    assert "😄" in body or "zensical" not in sys.modules
    assert "settings from" in capsys.readouterr().out


def test_clean_reports_a_directory_that_is_not_there(tmp_path, capsys, monkeypatch):
    """Deleting nothing and reporting success is how a typo hides."""
    monkeypatch.chdir(tmp_path)

    assert main(["clean", "--docs-dir", "no-such-dir"]) == 2
    assert "not a directory" in capsys.readouterr().err


def test_source_path_is_quoted_so_a_colon_cannot_break_the_front_matter(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page: draft.crv").write_text("# Page\n", encoding="utf-8")

    convert_tree(docs)
    body = (docs / "page: draft.md").read_text(encoding="utf-8")
    front_matter = yaml.safe_load(body.split("---")[1])

    assert front_matter[SOURCE_KEY].endswith("page: draft.crv")


def test_config_is_taken_from_the_environment_when_no_path_is_given(tmp_path, monkeypatch):
    """`build --config FILE` reaches the fence, which runs in another process."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    _write(
        elsewhere / "carve.toml",
        """
        [tool.zensical-carve]
        extensions = ["details"]
        """,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(config.CONFIG_ENV, str(elsewhere / "carve.toml"))

    assert config.load().extensions == ("details",)


def test_resolved_settings_round_trip_through_the_environment(monkeypatch, tmp_path):
    """`build` renders pages itself and hands the answer to the child process."""
    settings = config.Settings(
        extensions=("details",), emoji="unicode", symbols={"crab": "🦀"}
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(config.SETTINGS_ENV, config.encode(settings))

    loaded = config.load()

    assert loaded.extensions == ("details",)
    assert loaded.emoji == "unicode"
    assert loaded.symbols == {"crab": "🦀"}


# --- Zensical's cache ------------------------------------------------------
#
# A Carve setting is not one of Zensical's cache inputs. Measured on 0.0.56:
# switching `emoji` from twemoji to unicode and rebuilding served the twemoji
# page again, because index.md had not changed.


def test_a_first_build_in_a_clean_tree_does_not_ask_for_a_clean(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert preprocess._settings_changed('{"emoji": "none"}') is False


def test_a_changed_setting_asks_for_a_clean(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    preprocess._record_settings('{"emoji": "twemoji"}')

    assert preprocess._settings_changed('{"emoji": "twemoji"}') is False
    assert preprocess._settings_changed('{"emoji": "unicode"}') is True


def test_an_existing_cache_without_a_stamp_asks_for_a_clean(tmp_path, monkeypatch):
    """A cache built before this package knew to record anything."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".cache").mkdir()

    assert preprocess._settings_changed('{"emoji": "none"}') is True
