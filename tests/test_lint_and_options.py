"""Lint findings, the `lint` subcommand, and per-extension options."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

import zensical_carve
from zensical_carve import config, fence, lint, render
from zensical_carve.preprocess import convert_tree, lint_tree, main

UNATTACHED = "para\n\n{#id .cls}\n"


def _write(path: Path, text: str) -> None:
    path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")


def _site(tmp_path: Path, table: str = "", page: str = UNATTACHED) -> Path:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.crv").write_text(page, encoding="utf-8")
    if table:
        _write(tmp_path / "zensical.toml", "[tool.zensical-carve]\n" + textwrap.dedent(table))
    return docs


# --- lint ------------------------------------------------------------------


def test_lint_returns_the_engine_findings():
    (finding,) = lint(UNATTACHED)
    assert finding["rule"] == "unattached-block-attribute"
    assert (finding["line"], finding["column"]) == (3, 1)


def test_lint_tree_locates_each_finding_on_its_page(tmp_path):
    docs = _site(tmp_path)
    outcome = lint_tree(docs)
    assert outcome.findings == [
        f"{docs / 'page.crv'}:3:1: unattached-block-attribute: "
        + lint(UNATTACHED)[0]["message"]
    ]
    assert not (docs / "page.md").exists()


def test_convert_tree_lints_only_when_asked(tmp_path):
    docs = _site(tmp_path)
    assert convert_tree(docs).findings == []
    assert len(convert_tree(docs, lint_pages=True).findings) == 1


def test_lint_subcommand_exits_one_on_a_finding(tmp_path, capsys, monkeypatch):
    _site(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert main(["lint"]) == 1
    assert "page.crv:3:1: unattached-block-attribute" in capsys.readouterr().err


def test_lint_subcommand_exits_zero_on_a_clean_tree(tmp_path, capsys, monkeypatch):
    _site(tmp_path, page="# Clean\n\ntext\n")
    monkeypatch.chdir(tmp_path)
    assert main(["lint"]) == 0
    assert capsys.readouterr().err == ""


def test_prepare_with_lint_warns_and_still_writes(tmp_path, capsys, monkeypatch):
    docs = _site(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert main(["prepare", "--lint"]) == 0
    assert "WARNING: " in capsys.readouterr().err
    assert (docs / "page.md").exists()


def test_lint_from_the_config_table(tmp_path, capsys, monkeypatch):
    _site(tmp_path, "lint = true\n")
    monkeypatch.chdir(tmp_path)
    assert main(["prepare"]) == 0
    assert "unattached-block-attribute" in capsys.readouterr().err


def _fake_zensical(tmp_path: Path, monkeypatch) -> Path:
    marker = tmp_path / "zensical-ran"
    script = tmp_path / "fake-zensical"
    script.write_text(
        f"#!{sys.executable}\nopen({str(marker)!r}, 'w').close()\n", encoding="utf-8"
    )
    script.chmod(0o755)
    monkeypatch.setenv("ZENSICAL", str(script))
    return marker


@pytest.mark.parametrize("flag", ["--strict", "-s"])
def test_strict_build_aborts_on_a_finding_before_zensical_runs(
    tmp_path, capsys, monkeypatch, flag
):
    _site(tmp_path)
    marker = _fake_zensical(tmp_path, monkeypatch)
    monkeypatch.chdir(tmp_path)
    assert main(["build", "--lint", "--", flag]) == 1
    assert "strict mode" in capsys.readouterr().err
    assert not marker.exists()


def test_non_strict_build_runs_zensical_despite_a_finding(tmp_path, monkeypatch):
    _site(tmp_path)
    marker = _fake_zensical(tmp_path, monkeypatch)
    monkeypatch.chdir(tmp_path)
    assert main(["build", "--lint"]) == 0
    assert marker.exists()


def test_strict_build_without_lint_runs_zensical(tmp_path, monkeypatch):
    _site(tmp_path)
    marker = _fake_zensical(tmp_path, monkeypatch)
    monkeypatch.chdir(tmp_path)
    assert main(["build", "--", "--strict"]) == 0
    assert marker.exists()


def test_lint_config_must_be_a_bool(tmp_path):
    _site(tmp_path, 'lint = "yes"\n')
    with pytest.raises(config.ConfigError, match="lint"):
        config.load(start=tmp_path)


# --- extension options -----------------------------------------------------


def test_config_splits_names_and_options(tmp_path):
    _site(
        tmp_path,
        """
        extensions = ["details", { wikilinks = { css_class = "wl" } }, { tabs = {} }]
        """,
    )
    settings = config.load(start=tmp_path)
    assert settings.extensions == ("details", "wikilinks", "tabs")
    assert settings.extension_options == {"wikilinks": {"css_class": "wl"}}


@pytest.mark.parametrize(
    "entry",
    ['{ a = {}, b = {} }', '{ wikilinks = "wl" }', "3"],
)
def test_a_malformed_extensions_entry_is_refused(tmp_path, entry):
    _site(tmp_path, f"extensions = [{entry}]\n")
    with pytest.raises(config.ConfigError, match="extensions"):
        config.load(start=tmp_path)


def test_render_passes_options_to_the_engine():
    html = render(
        "[[Foo Bar]]\n",
        extensions=["wikilinks"],
        extension_options={"wikilinks": {"css_class": "wl", "new_window": True}},
    )
    assert 'class="wl"' in html
    assert 'target="_blank"' in html


def test_render_drops_options_for_an_extension_not_enabled():
    html = render(
        "[[Foo Bar]]\n",
        extensions=["details"],
        extension_options={"wikilinks": {"css_class": "wl"}},
    )
    assert 'class="wl"' not in html


def test_options_reach_a_whole_page(tmp_path, monkeypatch):
    docs = _site(
        tmp_path,
        'extensions = [{ wikilinks = { css_class = "wl" } }]\n',
        page="[[Foo Bar]]\n",
    )
    monkeypatch.chdir(tmp_path)
    assert main(["prepare"]) == 0
    assert 'class="wl"' in (docs / "page.md").read_text(encoding="utf-8")


def test_options_reach_a_carve_fence(tmp_path, monkeypatch):
    _site(tmp_path, 'extensions = [{ wikilinks = { css_class = "wl" } }]\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(config.SETTINGS_ENV, raising=False)
    monkeypatch.delenv(config.CONFIG_ENV, raising=False)
    zensical_carve._runtime.cache_clear()
    try:
        html = fence("[[Foo Bar]]\n", "carve", "carve", {}, None)
    finally:
        zensical_carve._runtime.cache_clear()
    assert 'class="wl"' in html


def test_options_and_lint_round_trip_through_the_environment(monkeypatch, tmp_path):
    settings = config.Settings(
        extensions=("wikilinks",),
        extension_options={"wikilinks": {"css_class": "wl"}},
        lint=True,
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(config.SETTINGS_ENV, config.encode(settings))
    loaded = config.load()
    assert loaded.extension_options == {"wikilinks": {"css_class": "wl"}}
    assert loaded.lint is True


def test_an_extension_flag_drops_the_configured_options(tmp_path, monkeypatch):
    docs = _site(
        tmp_path,
        'extensions = [{ wikilinks = { css_class = "wl" } }]\n',
        page="[[Foo Bar]]\n",
    )
    monkeypatch.chdir(tmp_path)
    assert main(["prepare", "--extension", "wikilinks"]) == 0
    body = (docs / "page.md").read_text(encoding="utf-8")
    assert 'class="wikilink"' in body
    assert 'class="wl"' not in body
