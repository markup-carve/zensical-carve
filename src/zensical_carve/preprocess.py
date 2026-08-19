"""Render whole ``.crv`` pages into ``.md`` pages Zensical can build.

Zensical discovers pages by extension. A ``.crv`` file in the docs directory is
not parsed - it is copied into the output as a static file, which was measured
against Zensical 0.0.56 rather than assumed. So a whole Carve page has to exist
as ``.md`` by the time the build runs.

What this writes is a Markdown file whose body is the rendered HTML. That is
not a workaround for Markdown's benefit - Python-Markdown passes a block-level
raw HTML through untouched, nested indentation and tables included - it is how
the page reaches Zensical's own pipeline (front matter, navigation, search
indexing, the table of contents) without Carve having to reimplement any of it.

Front matter is lifted rather than rendered. Carve strips its own front matter
from the HTML, so the block is parsed out here and re-emitted at the top of the
generated file, where Zensical reads ``title`` and the rest.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Sequence

from . import CarveError, render
from .theme import adapt

__all__ = ["GENERATED_MARKER", "convert", "convert_tree", "clean_tree", "main"]

GENERATED_MARKER = "zensical_carve: generated"
"""Written into every generated file, and required before one is deleted.

It is a real YAML KEY rather than a comment on purpose. Zensical only strips a
front matter block when it parses to a dict (`zensical/markdown/render.py`), so
a block holding nothing but a comment parses to None, is left in the body, and
renders as a thematic break followed by a heading.
"""

_FRONT_MATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n(?:---|\.\.\.)[ \t]*\r?\n", re.DOTALL)


def _split_front_matter(source: str) -> tuple[str, str]:
    """Return ``(front_matter_body, rest)``, with an empty string for neither."""
    match = _FRONT_MATTER.match(source)
    if not match:
        return "", source
    return match.group(1), source[match.end() :]


def convert(
    source: str,
    *,
    extensions: Sequence[str] | None = None,
    theme: bool = True,
) -> str:
    """Render one Carve document into the text of a Markdown page.

    With ``theme`` (the default), headings and code blocks are handed back to
    Zensical as Markdown so the table of contents, the permalinks and the
    highlighting pipeline work - see :mod:`zensical_carve.theme`. Pass
    ``theme=False`` for the raw HTML, which is higher fidelity and less
    integrated.
    """
    front_matter, _ = _split_front_matter(source)
    html = render(source, extensions=extensions)
    if theme:
        html = adapt(html)

    head = ["---"]
    if front_matter:
        head.append(front_matter)
    head.append(GENERATED_MARKER)
    head.append("---")
    return "\n".join(head) + "\n\n" + html.rstrip("\n") + "\n"


def _is_generated(path: Path) -> bool:
    """A generated page carries the marker in its front matter."""
    try:
        with path.open(encoding="utf-8") as handle:
            head = handle.read(4096)
    except OSError:
        return False
    front_matter, _ = _split_front_matter(head)
    return GENERATED_MARKER in front_matter


def _sources(docs_dir: Path) -> Iterable[Path]:
    yield from sorted(docs_dir.rglob("*.crv"))


def convert_tree(
    docs_dir: Path,
    *,
    extensions: Sequence[str] | None = None,
    force: bool = False,
    theme: bool = True,
) -> list[Path]:
    """Render every ``.crv`` under ``docs_dir`` to a sibling ``.md``.

    An existing ``.md`` that this tool did not write is left alone and reported,
    rather than overwritten: a hand-written page and a generated one can share a
    stem by accident, and silently replacing the author's file is the worse
    failure. ``force`` overrides that.
    """
    written: list[Path] = []
    for source_path in _sources(docs_dir):
        target = source_path.with_suffix(".md")
        if target.exists() and not _is_generated(target) and not force:
            print(
                f"zensical-carve: {target} exists and was not generated here - skipping."
                " Rename it, or pass --force.",
                file=sys.stderr,
            )
            continue
        text = convert(
            source_path.read_text(encoding="utf-8"),
            extensions=extensions,
            theme=theme,
        )
        target.write_text(text, encoding="utf-8")
        written.append(target)
    return written


def clean_tree(docs_dir: Path) -> list[Path]:
    """Delete the generated pages, and only those."""
    removed: list[Path] = []
    for source_path in _sources(docs_dir):
        target = source_path.with_suffix(".md")
        if target.exists() and _is_generated(target):
            target.unlink()
            removed.append(target)
    return removed


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--docs-dir",
        default="docs",
        type=Path,
        help="the documentation directory to walk (default: docs)",
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the ``zensical-carve`` command."""
    parser = argparse.ArgumentParser(
        prog="zensical-carve",
        description="Render .crv pages so Zensical can build them.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare", help="render every .crv page to .md")
    _add_common(prepare)
    prepare.add_argument(
        "--extension",
        action="append",
        dest="extensions",
        metavar="NAME",
        help="enable a Carve extension; repeat for several",
    )
    prepare.add_argument(
        "--force",
        action="store_true",
        help="overwrite a .md this tool did not generate",
    )
    prepare.add_argument(
        "--raw-html",
        action="store_true",
        help="emit Carve's HTML verbatim, without handing headings and code"
        " blocks back to the theme",
    )

    clean = sub.add_parser("clean", help="delete the generated .md pages")
    _add_common(clean)

    build = sub.add_parser("build", help="prepare, then run `zensical build`")
    _add_common(build)
    build.add_argument(
        "--extension", action="append", dest="extensions", metavar="NAME",
        help="enable a Carve extension; repeat for several",
    )
    build.add_argument("--force", action="store_true", help="see `prepare --force`")
    build.add_argument(
        "--raw-html", action="store_true", help="see `prepare --raw-html`"
    )
    build.add_argument(
        "rest", nargs=argparse.REMAINDER, help="arguments passed to `zensical build`"
    )

    args = parser.parse_args(argv)
    docs_dir: Path = args.docs_dir
    if not docs_dir.is_dir():
        print(f"zensical-carve: {docs_dir} is not a directory", file=sys.stderr)
        return 2

    if args.command == "clean":
        for path in clean_tree(docs_dir):
            print(f"removed {path}")
        return 0

    try:
        written = convert_tree(
            docs_dir,
            extensions=args.extensions,
            force=args.force,
            theme=not args.raw_html,
        )
    except CarveError as error:
        print(f"zensical-carve: {error}", file=sys.stderr)
        return 1

    for path in written:
        print(f"wrote {path}")

    if args.command == "prepare":
        return 0

    rest = [item for item in args.rest if item != "--"]
    return subprocess.call([os.environ.get("ZENSICAL", "zensical"), "build", *rest])


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
