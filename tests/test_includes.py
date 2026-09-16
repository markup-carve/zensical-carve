"""One include policy, read from one table, for pages and for fences.

These need an engine that exposes ``carve.render_with_includes``. The engine
pinned in ``constraints-ci.txt`` predates it, so the ``includes`` CI job
installs one that has it; the skip below is what keeps the pinned job honest
about not having measured this.
"""

from __future__ import annotations

import os
from pathlib import Path

import carve
import pytest

import zensical_carve
from zensical_carve import CarveError, config, preprocess

pytestmark = pytest.mark.skipif(
    not hasattr(carve, "render_with_includes"),
    reason="installed carve-lang exposes no render_with_includes",
)


@pytest.fixture()
def site(tmp_path):
    docs = tmp_path / "docs"
    (docs / "sub").mkdir(parents=True)
    (tmp_path / "outside").mkdir()
    (docs / "sub" / "frag.crv").write_text("fragment with :crv:\n", encoding="utf-8")
    (tmp_path / "outside" / "secret.crv").write_text(
        "UNCONTAINED BODY\n", encoding="utf-8"
    )
    return tmp_path


def _settings(site, **values):
    return config.Settings(docs_dir=site / "docs", **values)


def _page(site, name, source):
    path = site / "docs" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def _convert(site, name, source, root, **kwargs):
    path = _page(site, name, source)
    return preprocess.convert(
        source, source_path=path, include_root=root, theme=False, **kwargs
    )


# --- the switch ------------------------------------------------------------


def test_a_directive_stays_literal_without_a_root(site):
    text = _convert(site, "index.crv", "{{ sub/frag.crv }}\n", None)
    assert "{{ sub/frag.crv }}" in text
    assert "fragment" not in text


def test_a_root_expands_the_directive(site):
    root = str((site / "docs").resolve())
    text = _convert(site, "index.crv", "{{ sub/frag.crv }}\n", root)
    assert "fragment" in text
    assert "{{ sub/frag.crv }}" not in text


# --- the root --------------------------------------------------------------


def test_expansion_is_off_until_the_table_asks(site):
    assert config.containment_root(_settings(site)) is None


def test_the_default_root_is_the_docs_directory(site):
    root = config.containment_root(_settings(site, includes=True))
    assert root == str((site / "docs").resolve())


def test_a_configured_root_is_handed_back_as_written(site):
    """Resolving it here is what would stop the engine ever refusing it."""
    settings = _settings(site, includes=True, include_root="fragments")
    assert config.containment_root(settings) == "fragments"


def test_a_relative_root_is_refused_by_the_engine(site):
    with pytest.raises(CarveError) as caught:
        _convert(site, "index.crv", "{{ sub/frag.crv }}\n", "fragments")
    assert "absolute" in str(caught.value)


def test_a_wider_root_reaches_the_engine(site):
    text = _convert(
        site, "index.crv", "{{ ../outside/secret.crv }}\n", str(site.resolve())
    )
    assert "UNCONTAINED BODY" in text


# --- denials ---------------------------------------------------------------


def test_traversal_out_of_the_root_is_not_expanded(site):
    root = str((site / "docs").resolve())
    text = _convert(site, "index.crv", "{{ ../outside/secret.crv }}\n", root)
    assert "UNCONTAINED BODY" not in text


def test_the_reported_warning_does_not_say_which_denial_it_was(site, capsys):
    """Spec I7: one warning for both, so a page cannot probe the filesystem."""
    root = str((site / "docs").resolve())
    _convert(site, "index.crv", "{{ ../outside/secret.crv }}\n", root)
    lines = [
        line
        for line in capsys.readouterr().err.splitlines()
        if "include-unresolved" in line
    ]
    assert lines, "a refused include reported nothing"
    assert not any("outside-root" in line for line in lines)


def test_the_denial_class_is_still_reported(site, capsys):
    root = str((site / "docs").resolve())
    source = "{{ ../outside/secret.crv }}\n\n{{ nope.crv }}\n"
    _convert(site, "index.crv", source, root)
    err = capsys.readouterr().err
    assert "outside-root" in err
    assert "not-found" in err


def test_a_warning_names_the_page_that_asked(site, capsys):
    """The page has to be on the WARNING line.

    An earlier version asserted only that the page name appeared somewhere in
    the output, which the denial-class line carries too - so it stayed green
    with the warnings dropped entirely.
    """
    root = str((site / "docs").resolve())
    _convert(site, "guide.crv", "{{ nope.crv }}\n", root)
    lines = capsys.readouterr().err.splitlines()
    assert any("guide.crv" in line and "include-unresolved" in line for line in lines)


def test_the_engine_reported_location_stays_relative_to_the_root(site, capsys):
    """A page below a narrowed root is where an absolute identity would leak one.

    The build prefixes its own messages with the page it read, which is its own
    path to print. What must not become a host path is the location the ENGINE
    reports, because that one also names included children.
    """
    root = str((site / "docs" / "sub").resolve())
    _convert(site, "index.crv", "{{ nope.crv }}\n", root)
    err = capsys.readouterr().err
    assert f"{os.pardir}{os.sep}index.crv: include-unresolved" in err


# --- what the engine is asked to do ---------------------------------------


def test_a_path_resolves_against_the_page_that_wrote_it(site):
    root = str((site / "docs").resolve())
    text = _convert(site, "sub/page.crv", "{{ frag.crv }}\n", root)
    assert "fragment" in text


def test_nested_relative_paths_resolve_against_the_including_file(site):
    (site / "docs" / "sub" / "deep").mkdir()
    (site / "docs" / "sub" / "deep" / "inner.crv").write_text(
        "inner text\n", encoding="utf-8"
    )
    (site / "docs" / "sub" / "frag.crv").write_text(
        "{{ deep/inner.crv }}\n", encoding="utf-8"
    )
    root = str((site / "docs").resolve())
    text = _convert(site, "index.crv", "{{ sub/frag.crv }}\n", root)
    assert "inner text" in text


def test_a_cycle_degrades_instead_of_hanging(site, capsys):
    (site / "docs" / "a.crv").write_text("A {{ b.crv }}\n", encoding="utf-8")
    (site / "docs" / "b.crv").write_text("B {{ a.crv }}\n", encoding="utf-8")
    root = str((site / "docs").resolve())
    text = _convert(site, "index.crv", "{{ a.crv }}\n", root)
    assert "A B" in text
    assert "include-cycle" in capsys.readouterr().err


def test_the_symbol_map_reaches_an_included_child(site):
    root = str((site / "docs").resolve())
    text = _convert(site, "index.crv", "{{ sub/frag.crv }}\n", root, symbols={"crv": "CARVE"})
    assert "CARVE" in text
    assert ":crv:" not in text


def test_the_extension_set_reaches_an_included_child(site):
    (site / "docs" / "sub" / "frag.crv").write_text("# Child\n", encoding="utf-8")
    root = str((site / "docs").resolve())
    text = _convert(
        site, "index.crv", "{{ sub/frag.crv }}\n", root, extensions=["heading_permalinks"]
    )
    assert "permalink" in text


# --- one policy, both seams ------------------------------------------------


def test_the_tree_walk_carries_the_root_to_every_page(site, capsys):
    _page(site, "index.crv", "{{ sub/frag.crv }}\n")
    root = str((site / "docs").resolve())
    outcome = preprocess.convert_tree(site / "docs", include_root=root, theme=False)
    written = {path.name: path.read_text(encoding="utf-8") for path in outcome.written}
    assert "fragment" in written["index.md"]


def test_the_fence_reads_the_same_table_the_pages_do(site):
    """The fence path and the page path must not diverge in silence."""
    encoded = config.encode(
        config.Settings(includes=True, include_root="/srv/fragments")
    )
    os.environ["ZENSICAL_CARVE_SETTINGS"] = encoded
    try:
        settings = config.load()
    finally:
        del os.environ["ZENSICAL_CARVE_SETTINGS"]
    assert settings.includes is True
    assert settings.include_root == "/srv/fragments"


def test_a_fence_leaves_the_directive_literal_and_says_so(site, capsys, monkeypatch):
    settings = config.Settings(includes=True, docs_dir=site / "docs")
    monkeypatch.setattr(zensical_carve, "_runtime", lambda: (settings, None, None))
    zensical_carve._note_fence_includes.cache_clear()
    html = zensical_carve.fence("{{ sub/frag.crv }}\n", "carve", "carve", {}, None)
    assert "{{ sub/frag.crv }}" in html
    assert "stays literal inside one" in capsys.readouterr().err


# --- configuration ---------------------------------------------------------


def test_the_table_reads_both_keys(site):
    path = site / "zensical.toml"
    path.write_text(
        "[tool.zensical-carve]\nincludes = true\ninclude-root = '/srv/fragments'\n",
        encoding="utf-8",
    )
    settings = config.load(path)
    assert settings.includes is True
    assert settings.include_root == "/srv/fragments"


def test_a_non_boolean_switch_is_refused(site):
    path = site / "zensical.toml"
    path.write_text("[tool.zensical-carve]\nincludes = 'yes'\n", encoding="utf-8")
    with pytest.raises(config.ConfigError) as caught:
        config.load(path)
    assert "includes" in str(caught.value)
