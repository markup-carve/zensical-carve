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

Every generated page also records the file it came from. Zensical validates
links and reports them against the file it read, which is the GENERATED page -
measured on 0.0.56, where a broken link written in ``page.crv`` is reported at
``page.md:7:15``, pointing at a line of HTML the author never wrote. The key
is what turns that back into an answerable question, and the warning printed
after a build says so.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from . import CarveError, config, render, symbols as symbol_module
from .config import ConfigError, Settings
from .theme import adapt

__all__ = [
    "GENERATED_MARKER",
    "SOURCE_KEY",
    "Outcome",
    "convert",
    "convert_tree",
    "clean_tree",
    "main",
]

GENERATED_MARKER = "zensical_carve: generated"
"""Written into every generated file, and required before one is deleted.

It is a real YAML KEY rather than a comment on purpose. Zensical only strips a
front matter block when it parses to a dict (`zensical/markdown/render.py`), so
a block holding nothing but a comment parses to None, is left in the body, and
renders as a thematic break followed by a heading.
"""

SOURCE_KEY = "zensical_carve_source"
"""Records the ``.crv`` a generated page came from.

Zensical attributes every warning to the file it read, and for a Carve page
that file is the generated one. A reader who lands on ``page.md:7:15`` needs
one hop back to the source, and this key is it.
"""


@dataclass
class Outcome:
    """What one pass over the tree did.

    A failing page does not stop the others: a site is usually built from many
    pages, and reporting all of the broken ones costs one pass while reporting
    the first one costs as many passes as there are mistakes.
    """

    written: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)
    failed: list[tuple[Path, str]] = field(default_factory=list)

    def __bool__(self) -> bool:  # pragma: no cover - convenience only
        return bool(self.written)


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
    symbols: Mapping[str, str] | None = None,
    source_path: Path | None = None,
) -> str:
    """Render one Carve document into the text of a Markdown page.

    With ``theme`` (the default), headings and code blocks are handed back to
    Zensical as Markdown so the table of contents, the permalinks and the
    highlighting pipeline work - see :mod:`zensical_carve.theme`. Pass
    ``theme=False`` for the raw HTML, which is higher fidelity and less
    integrated.
    """
    front_matter, _ = _split_front_matter(source)
    html = render(source, extensions=extensions, symbols=symbols)
    if theme:
        html = adapt(html)

    head = ["---"]
    if front_matter:
        head.append(front_matter)
    head.append(GENERATED_MARKER)
    if source_path is not None:
        # A quoted scalar, because a file name may hold a colon or a `#` and
        # an unquoted one would then parse as a mapping or lose its tail. YAML
        # is a superset of JSON, so a JSON string is a valid YAML scalar.
        head.append(f"{SOURCE_KEY}: {json.dumps(source_path.as_posix())}")
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
    symbols: Mapping[str, str] | None = None,
) -> Outcome:
    """Render every ``.crv`` under ``docs_dir`` to a sibling ``.md``.

    An existing ``.md`` that this tool did not write is left alone and reported,
    rather than overwritten: a hand-written page and a generated one can share a
    stem by accident, and silently replacing the author's file is the worse
    failure. ``force`` overrides that.

    A page the engine refuses is recorded against ITS OWN path and the walk
    continues. Before this, one bad page produced one message with no file name
    in it, on a tree of any size.
    """
    outcome = Outcome()
    for source_path in _sources(docs_dir):
        target = source_path.with_suffix(".md")
        if target.exists() and not _is_generated(target) and not force:
            print(
                f"zensical-carve: {target} exists and was not generated here - skipping."
                " Rename it, or pass --force.",
                file=sys.stderr,
            )
            outcome.skipped.append(target)
            continue
        try:
            text = convert(
                source_path.read_text(encoding="utf-8"),
                extensions=extensions,
                theme=theme,
                symbols=symbols,
                source_path=source_path,
            )
        except CarveError as error:
            outcome.failed.append((source_path, str(error)))
            continue
        except UnicodeDecodeError as error:
            # A page in another encoding reaches here rather than as an OSError,
            # and the default message names a codec and a byte offset without
            # ever naming the file.
            outcome.failed.append(
                (source_path, f"not valid UTF-8 ({error.reason} at byte {error.start})")
            )
            continue
        except OSError as error:
            outcome.failed.append((source_path, str(error)))
            continue
        try:
            target.write_text(text, encoding="utf-8")
        except OSError as error:
            # A read-only directory or a full disk stops this page, not the walk.
            outcome.failed.append((source_path, f"could not write {target}: {error}"))
            continue
        outcome.written.append(target)
    return outcome


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
        default=None,
        type=Path,
        help="the documentation directory to walk (default: docs)",
    )
    parser.add_argument(
        "--config",
        default=None,
        type=Path,
        metavar="FILE",
        help="read [tool.zensical-carve] from FILE instead of searching for it",
    )


def _add_render_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--extension",
        action="append",
        dest="extensions",
        metavar="NAME",
        help="enable a Carve extension; repeat for several",
    )
    parser.add_argument(
        "--emoji",
        choices=config.EMOJI_MODES,
        default=None,
        help="how a `:name:` symbol renders (default: none)",
    )
    parser.add_argument(
        "--symbols",
        default=None,
        type=Path,
        metavar="FILE",
        help="a JSON object mapping a symbol name to what it renders as",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite a .md this tool did not generate",
    )
    parser.add_argument(
        "--raw-html",
        action="store_true",
        help="emit Carve's HTML verbatim, without handing headings and code"
        " blocks back to the theme",
    )


def _resolve(args: argparse.Namespace) -> Settings:
    """File first, then the flags that were actually passed."""
    settings = config.load(args.config)
    extra: dict[str, object] = {}
    if args.symbols is not None:
        extra["symbols"] = {
            **settings.symbols,
            **config.read_symbols(args.symbols),
        }
    return config.merge(
        settings,
        docs_dir=args.docs_dir,
        extensions=tuple(args.extensions) if args.extensions else None,
        emoji=args.emoji,
        force=args.force,
        raw_html=args.raw_html,
        **extra,
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
    _add_render_options(prepare)

    clean = sub.add_parser("clean", help="delete the generated .md pages")
    _add_common(clean)

    build = sub.add_parser("build", help="prepare, then run `zensical build`")
    _add_common(build)
    _add_render_options(build)
    build.add_argument(
        "rest", nargs=argparse.REMAINDER, help="arguments passed to `zensical build`"
    )

    args = parser.parse_args(argv)

    if args.command == "clean":
        docs_dir = _clean_docs_dir(args)
        if docs_dir is None:
            return 2
        for path in clean_tree(docs_dir):
            print(f"removed {path}")
        return 0

    try:
        settings = _resolve(args)
    except ConfigError as error:
        print(f"zensical-carve: {error}", file=sys.stderr)
        return 2

    docs_dir = settings.docs_dir
    if not docs_dir.is_dir():
        print(f"zensical-carve: {docs_dir} is not a directory", file=sys.stderr)
        return 2

    if settings.source is not None:
        print(f"zensical-carve: settings from {settings.source}")

    try:
        symbols = symbol_module.build(settings.emoji, settings.symbols)
    except ValueError as error:  # pragma: no cover - choices() guards the CLI
        print(f"zensical-carve: {error}", file=sys.stderr)
        return 2

    outcome = convert_tree(
        docs_dir,
        extensions=settings.extensions,
        force=settings.force,
        theme=not settings.raw_html,
        symbols=symbols,
    )

    for path in outcome.written:
        print(f"wrote {path}")
    for path, message in outcome.failed:
        print(f"zensical-carve: {path}: {message}", file=sys.stderr)

    if outcome.failed:
        return 1

    if outcome.written:
        print(
            "zensical-carve: a build warning about one of these .md pages"
            f" comes from the .crv named in its {SOURCE_KEY}.",
        )

    if args.command == "prepare":
        return 0

    rest = [item for item in args.rest if item != "--"]
    # The fence runs inside `zensical build`, in another process, and would
    # otherwise re-read the file and lose every flag passed here - so a block
    # and a page in one build could render differently.
    environment = dict(os.environ)
    resolved = config.encode(settings)
    environment[config.SETTINGS_ENV] = resolved

    # Zensical caches a rendered page by its own inputs, and a Carve setting is
    # not one of them: measured on 0.0.56, where switching `emoji` from twemoji
    # to unicode and rebuilding served the twemoji page again. A whole `.crv`
    # page escapes this because its `.md` was just rewritten, so it is the
    # fenced blocks that would go stale.
    if _settings_changed(resolved) and "--clean" not in rest and "-c" not in rest:
        rest = ["--clean", *rest]

    code = subprocess.call(
        [os.environ.get("ZENSICAL", "zensical"), "build", *rest], env=environment
    )
    if code == 0:
        _record_settings(resolved)
    return code


CACHE_STAMP = Path(".cache") / "zensical-carve.json"
"""What the last successful build rendered with, beside Zensical's own cache.

It lives in the cache directory on purpose: `zensical build --clean` empties
that directory, so a hand-cleaned cache also forgets this and the next build
starts from nothing rather than from a claim about a cache that is gone.
"""


def _settings_changed(resolved: str) -> bool:
    try:
        return CACHE_STAMP.read_text(encoding="utf-8") != resolved
    except OSError:
        # No stamp is not "unchanged": either this is the first build, or the
        # cache was cleaned, and both are cheap to be wrong about only once.
        return CACHE_STAMP.parent.exists()


def _record_settings(resolved: str) -> None:
    try:
        CACHE_STAMP.parent.mkdir(parents=True, exist_ok=True)
        CACHE_STAMP.write_text(resolved, encoding="utf-8")
    except OSError:  # pragma: no cover - a read-only project directory
        pass


def _clean_docs_dir(args: argparse.Namespace) -> Path | None:
    """`clean` reads the configuration too, but only for the directory.

    A directory named on the command line is still checked: deleting nothing
    and reporting success is the failure mode that hides a typo.
    """
    if args.docs_dir is not None:
        docs_dir = args.docs_dir
    else:
        try:
            docs_dir = config.load(args.config).docs_dir
        except ConfigError as error:
            print(f"zensical-carve: {error}", file=sys.stderr)
            return None
    if not docs_dir.is_dir():
        print(f"zensical-carve: {docs_dir} is not a directory", file=sys.stderr)
        return None
    return docs_dir


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
