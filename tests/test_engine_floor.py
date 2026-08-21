"""Whether the engine this package RESOLVES is one the floor actually admits.

`pyproject.toml` declares a range, so what gets installed is whatever PyPI
serves inside it. That is not something this repository can read off its own
manifest - the manifest looks current either way - and no other test here
notices: all 63 of them passed against a vulnerable engine exactly as well as
against a patched one, which is what this file is for.

The defect the floor was set for is carve-lang 0.1.0's: a list-valued URL
attribute was probed only on its FIRST entry, so a payload in the second one was
never sanitized. Measured through this package's own ``render``:

    carve-lang 0.1.0 -> <img src="safe.png" alt="x"
                             srcset="safe.png 1x, javascript:alert(1) 2x">
    carve-lang 0.1.1 -> <img src="safe.png" alt="x" srcset="">

So `carve-lang>=0.1.1` is a real statement about the oldest engine this package
works with. The range is open at the top, and a future engine could regress it,
which is why this is an assertion rather than a comment.

Raising the floor is a decision about what stopped working, never about what is
newest - see `constraints-ci.txt` for how the floor and the CI pin move
separately.
"""

from __future__ import annotations

from importlib.metadata import version

from zensical_carve import render

PAYLOAD = '![x](safe.png){srcset="safe.png 1x, javascript:alert(1) 2x"}\n'


def _engine() -> str:
    try:
        return version("carve-lang")
    except Exception:  # pragma: no cover - only reached on a broken install
        return "unknown"


def test_the_resolved_engine_sanitizes_list_valued_url_attributes():
    html = render(PAYLOAD)
    assert "javascript:" not in html.lower(), (
        f"the installed carve-lang ({_engine()}) emitted an unsanitized "
        f"javascript: URL in a list-valued attribute: {html.strip()}"
    )


def test_the_payload_still_reaches_the_engine():
    """The probe above is only evidence if the engine actually renders it.

    Without this, an engine that raised on the input - or one whose ``to_html``
    returned an empty string - would satisfy the assertion above by producing
    nothing, and the floor would be reported as sound without ever having been
    measured.
    """
    html = render(PAYLOAD)
    assert "<img" in html, f"the engine did not render an image at all: {html!r}"
    assert "safe.png" in html, f"the engine dropped the source URL: {html!r}"
