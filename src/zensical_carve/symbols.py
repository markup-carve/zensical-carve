"""Turn `:smile:` into an emoji, the way the rest of the site already does.

Carve parses `:name:` as a symbol in core - no extension needed - but the map
from a name to what it renders as is a render option, and a document that
reaches the engine without one renders `:smile:` as its own source text. Every
Material for MkDocs project has twemoji on, so this is the one default a
migrating project notices immediately.

The names come from Zensical's own emoji index, which is the same database its
Markdown pages use. That matters more than shipping a list here would: a
`:smile:` in a Markdown page and a `:smile:` in a Carve page on the same site
resolve through one source, so they cannot drift apart.

Two modes, because the choice is a real one:

`unicode`
    The character itself. No network, no images, and it inherits the page's
    font - which on Linux is often no color emoji font at all.

`twemoji`
    The `<img class="twemoji">` element Zensical emits for a Markdown page,
    pointing at the same CDN and carrying the same class, so the theme's sizing
    applies and the two page types look identical.
"""

from __future__ import annotations

import functools
from typing import Any, Mapping

__all__ = ["CDN", "emoji_map", "build"]

CDN = "https://cdn.jsdelivr.net/gh/jdecked/twemoji@16.0.1/assets/svg/"
"""Fallback only - the value is read from `pymdownx.emoji` when it is there."""


def _cdn() -> str:
    try:
        from pymdownx.emoji import TWEMOJI_SVG_CDN
    except ImportError:  # pragma: no cover - pymdownx ships with zensical
        return CDN
    return str(TWEMOJI_SVG_CDN)


@functools.lru_cache(maxsize=1)
def _index() -> Mapping[str, Any]:
    """Zensical's emoji database, or an empty map when Zensical is absent.

    The package is an optional dependency here: rendering a Carve document does
    not need Zensical, and a project that only uses the fence may not have the
    index available at all.
    """
    try:
        from zensical.extensions.emoji import twemoji
    except ImportError:
        return {}
    try:
        return twemoji({}, {}).get("emoji", {})
    except Exception:  # pragma: no cover - a database that will not load
        return {}


def _character(unicode_points: str) -> str:
    return "".join(chr(int(point, 16)) for point in unicode_points.split("-"))


@functools.lru_cache(maxsize=4)
def emoji_map(mode: str) -> dict[str, str]:
    """Return a Carve symbol map for ``mode``.

    Keys are bare names - Carve matches `:name:` and hands `name` to the map -
    while Zensical's index is keyed by the colon form.

    Entries without a codepoint are icons rather than emoji (`:material-home:`
    and its ten thousand siblings), which resolve to an SVG file on disk. They
    are left out: reading ten thousand files to build one map costs more than
    the feature is worth, and an icon that stays literal is visibly missing
    rather than silently wrong.
    """
    if mode == "none":
        return {}
    if mode not in ("unicode", "twemoji"):
        raise ValueError(f"unknown emoji mode: {mode}")

    cdn = _cdn()
    out: dict[str, str] = {}
    for shortname, entry in _index().items():
        points = entry.get("unicode")
        if not points:
            continue
        name = shortname.strip(":")
        character = _character(points)
        if mode == "unicode":
            out[name] = character
        else:
            out[name] = (
                f'<img alt="{character}" class="twemoji"'
                f' src="{cdn}{points}.svg" title="{shortname}" />'
            )
    return out


def build(mode: str, extra: Mapping[str, str] | None = None) -> dict[str, str] | None:
    """The map Carve is called with: the emoji set, then the project's own.

    ``None`` rather than an empty map when there is nothing to pass, so the
    engine keeps its own default behavior instead of being told "no symbols".
    """
    combined = dict(emoji_map(mode))
    if extra:
        combined.update(extra)
    return combined or None
