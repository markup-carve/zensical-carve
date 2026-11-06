"""Behavior that needs the carve-lang release built on the carve 0.1.14 rulings."""

from __future__ import annotations

from pathlib import Path

import carve
import pytest

from zensical_carve import config, render
from zensical_carve.preprocess import convert, main

pytestmark = pytest.mark.skipif(
    not hasattr(carve, "decision_trace"),
    reason="needs the carve-lang release that ships decision_trace",
)

CAPTIONED = "![A cat](cat.png)\n\nFigure 1: A cat.\n"


def _docs(tmp_path: Path, page: str, table: str = "") -> Path:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page.crv").write_text(page, encoding="utf-8")
    (tmp_path / "zensical.toml").write_text(
        f'site_name = "t"\n[tool.zensical-carve]\n{table}', encoding="utf-8"
    )
    return docs


def test_an_unclosed_opener_is_reported(capsys):
    source = "---\n\n# A page that meant a thematic break\n"
    assert render(source) == ""
    convert(source)
    assert "no `---` closes it" in capsys.readouterr().err


def test_a_closed_opener_is_not_reported(capsys):
    convert("---\ntitle: x\n---\nbody\n")
    assert "closes it" not in capsys.readouterr().err


def test_caption_hints_reach_the_linter(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _docs(tmp_path, CAPTIONED)
    assert main(["lint"]) == 0
    assert main(["lint", "--caption-hints"]) == 1
    assert "caption-looking-paragraph" in capsys.readouterr().err


def test_caption_hints_from_the_configuration_table(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _docs(tmp_path, CAPTIONED, "caption-hints = true\n")
    assert config.load().caption_hints is True
    assert main(["lint"]) == 1
    assert "caption-looking-paragraph" in capsys.readouterr().err


def test_caption_hints_must_be_a_boolean(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _docs(tmp_path, CAPTIONED, 'caption-hints = "yes"\n')
    with pytest.raises(config.ConfigError, match="caption-hints"):
        config.load()


@pytest.mark.parametrize(
    ("page", "rule"),
    [
        ("a\n\n---\n\nb\n", "thematic-break-spelling"),
        ("|=> Qty |= Name |\n| 1 | a |\n", "deprecated-cell-alignment"),
    ],
)
def test_retired_spellings_are_findings(tmp_path, monkeypatch, capsys, page, rule):
    monkeypatch.chdir(tmp_path)
    _docs(tmp_path, page)
    assert main(["lint"]) == 1
    assert rule in capsys.readouterr().err


def test_canonical_spellings_lint_clean(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _docs(tmp_path, "a\n\n***\n\nb\n\n|={>} Qty |= Name |\n| 1 | a |\n")
    assert main(["lint"]) == 0


def test_a_suppression_comment_silences_a_finding(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    page = "a\n\n%% carve-lint-disable-next-line thematic-break-spelling\n---\n\nb\n"
    _docs(tmp_path, page)
    assert main(["lint"]) == 0


def test_table_includes_select_rows_and_columns(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    docs = _docs(
        tmp_path,
        '{table}\n{{ plans.csv @code:csv @rows:3-3 @cols:"Plan" }}\n',
        "includes = true\n",
    )
    (docs / "plans.csv").write_text(
        "Plan,Seats\nFree,1\nTeam,10\nEnterprise,100\n", encoding="utf-8"
    )
    assert main(["prepare"]) == 0
    page = (docs / "page.md").read_text(encoding="utf-8")
    assert "Team" in page
    assert "Free" not in page and "Seats" not in page
