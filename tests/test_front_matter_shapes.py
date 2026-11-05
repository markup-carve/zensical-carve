"""Front matter is lifted exactly when the engine reads it as front matter."""

from __future__ import annotations

import pytest
import yaml

from zensical_carve import render
from zensical_carve.preprocess import convert

LIFTED = [
    "---\ntitle: Lifted\n---\nbody\n",
    "--- yaml\ntitle: Lifted\n---\nbody\n",
    "---yaml\ntitle: Lifted\n---\nbody\n",
    "--- YAML\ntitle: Lifted\n---\nbody\n",
    "--- yaml \ntitle: Lifted\n---\nbody\n",
    "--- \ntitle: Lifted\n---\nbody\n",
    "---\t\ntitle: Lifted\n---\nbody\n",
    "---\ntitle: Lifted\n---  \nbody\n",
    "---\ntitle: Lifted\n---",
    "---\r\ntitle: Lifted\r\n---\r\nbody\r\n",
    "---\ntitle: Lifted\n ---\nmore: x\n---\nbody\n",
]

NOT_FRONT_MATTER = [
    "---  yaml\ntitle: Lifted\n---\nbody\n",
    "---\tyaml\ntitle: Lifted\n---\nbody\n",
    "---y-a\ntitle: Lifted\n---\nbody\n",
    "  ---\ntitle: Lifted\n---\nbody\n",
]


def _meta(page: str) -> dict:
    return yaml.safe_load(page.split("---\n", 2)[1])


@pytest.mark.parametrize("source", LIFTED)
def test_engine_front_matter_reaches_zensical(source):
    assert "Lifted" not in render(source)
    assert _meta(convert(source))["title"] == "Lifted"


@pytest.mark.parametrize("source", NOT_FRONT_MATTER)
def test_text_the_engine_renders_is_not_lifted(source):
    assert "Lifted" in render(source)
    assert "title" not in _meta(convert(source))


def test_a_dotted_closer_does_not_close():
    page = convert("---\ntitle: Lifted\n...\nbody\n")
    assert "title" not in _meta(page)


def test_a_non_yaml_format_is_reported_and_not_lifted(capsys):
    page = convert("--- toml\ntitle = 'Lifted'\n---\nbody\n")
    assert "title" not in _meta(page)
    assert "format 'toml'" in capsys.readouterr().err


def test_empty_front_matter_is_dropped():
    page = convert("---\n---\nbody\n")
    assert _meta(page) == {"zensical_carve": "generated"}
    assert "<p>body</p>" in page


def test_a_keep_chomping_scalar_keeps_its_blank_lines():
    page = convert("---\ndescription: |+\n  hello\n\n\n---\nbody\n")
    assert _meta(page)["description"] == "hello\n\n\n"
