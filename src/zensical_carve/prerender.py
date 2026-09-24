"""Render a diagram once, at build time, instead of in every reader's browser.

Carve's `fenced-render` presets emit the block a client-side library picks up:
` ```mermaid ` becomes `<pre class="mermaid">`, and Mermaid turns it into a
picture after the page loads. That works, and it costs the reader a Javascript
payload, a layout shift when the picture replaces the text, and a moment where
the diagram's source is visible. Zensical tracks the same complaint as
[backlog#155](https://github.com/zensical/backlog/issues/155).

Rendering at build time removes all three. Two backends, neither of them a
default - a diagram source leaving the machine is the author's decision, not
this package's:

Kroki
    One HTTP service that speaks every diagram language here. `kroki.io` is
    public; `prerender-url` points at your own instance instead, which is the
    form to use in CI and for anything not public.

A command
    `prerender-command` runs a local binary per language - `mmdc`, `d2`,
    `dot`. Nothing leaves the machine.

A language that fails is left exactly as it was, so the page still works the
way it did before: the client-side library picks the block up as usual. A build
that must not silently fall back can read the warnings, which name the page.
"""

from __future__ import annotations

import hashlib
import html
import os
import re
import shlex
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Mapping, Sequence

__all__ = [
    "KROKI_LANGUAGES",
    "KROKI_URL",
    "Options",
    "apply",
    "cache_dir",
    "unsupported",
]

KROKI_URL = "https://kroki.io"

_USER_AGENT = "zensical-carve (+https://github.com/markup-carve/zensical-carve)"

TIMEOUT = 60
"""Seconds one diagram may take.

Measured against the public `kroki.io`: a graphviz graph came back in under a
second, and mermaid - which runs a headless browser - did not answer within 30.
A busy public instance is the slow case; a local one or a command is not.
"""

KROKI_LANGUAGES: dict[str, str] = {
    "mermaid": "mermaid",
    "d2": "d2",
    "graphviz": "graphviz",
    "plantuml": "plantuml",
    "wavedrom": "wavedrom",
    "vega-lite": "vegalite",
}
"""Carve's fence word on the left, Kroki's path segment on the right.

Carve draws two more - `chart` and `abc` - which Kroki does not serve. They are
rejected rather than quietly skipped, so a typo and an unsupported language
read differently.
"""

_XML_PROLOG = re.compile(r"<\?xml[^>]*\?>\s*|<!DOCTYPE[^>]*>\s*", re.IGNORECASE)


@dataclass(frozen=True)
class _Block:
    """One element whose class names a language somebody asked to prerender."""

    tag: str
    language: str
    start: int
    payload_start: int
    payload_end: int
    end: int


class _Finder(HTMLParser):
    """Locate diagram blocks by their class, whatever else the tag carries.

    A regex over the whole start tag is what broke here: it wanted
    ``class`` and nothing else, so carve-lang 0.1.2 adding `role` and
    `aria-label` made it match nothing - silently, because a block that never
    matched takes no path that can report anything. Reading the tag as a tag
    means an attribute added later is simply another attribute.

    Elements that are not `pre` are collected too. The engine moving the
    diagram onto a different tag is the next shape change of the same kind,
    and :func:`apply` turns that one into a warning instead of a silent pass.
    """

    def __init__(self, wanted: set[str]) -> None:
        super().__init__(convert_charrefs=False)
        self._wanted = wanted
        self.blocks: list[_Block] = []
        self._markup = ""
        self._lines: list[int] = []
        self._open: list[tuple[str, int, int] | None] = []

    def find(self, markup: str) -> list[_Block]:
        self._markup = markup
        self._lines = [0]
        for line in markup.split("\n"):
            self._lines.append(self._lines[-1] + len(line) + 1)
        self.feed(markup)
        self.close()
        return sorted(self.blocks, key=lambda block: block.start)

    def _offset(self) -> int:
        line, column = self.getpos()
        return self._lines[line - 1] + column

    def _language(self, attrs: list[tuple[str, str | None]]) -> str | None:
        for name, value in attrs:
            if name.lower() != "class" or not value:
                continue
            for token in value.split():
                if token in self._wanted:
                    return token
        return None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        language = self._language(attrs)
        if tag != "pre":
            if language is not None and not self._open:
                start = self._offset()
                self.blocks.append(_Block(tag, language, start, start, start, start))
            return
        if language is None or self._open:
            # An unlabelled `pre`, or one nested in a block already claimed.
            # Tracked either way, so its end tag closes the right element.
            self._open.append(None)
            return
        start = self._offset()
        self._open.append((language, start, start + len(self.get_starttag_text() or "")))

    def handle_endtag(self, tag: str) -> None:
        if tag != "pre" or not self._open:
            return
        entry = self._open.pop()
        if entry is None:
            return
        language, start, payload_start = entry
        payload_end = self._offset()
        closing = self._markup.find(">", payload_end)
        end = len(self._markup) if closing < 0 else closing + 1
        self.blocks.append(
            _Block("pre", language, start, payload_start, payload_end, end)
        )

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # `<pre class="mermaid"/>` holds no diagram, and the default handler
        # would open and close it, recording an empty payload.
        if tag != "pre":
            self.handle_starttag(tag, attrs)


def unsupported(options: "Options") -> list[str]:
    """Listed languages that nothing can draw: no Kroki service, no command.

    One definition for both entry points. The command line turns this into a
    refusal, because a typo there is worth stopping for; the fence turns it
    into a warning, because it runs inside `zensical build` and a configuration
    nit must not take a whole site down with it.
    """
    return [
        name
        for name in options.languages
        if name not in KROKI_LANGUAGES and name not in options.commands
    ]


def cache_dir() -> Path:
    """Where a rendered diagram is kept between builds.

    NOT inside Zensical's `.cache`, which looked tidier and was wrong: pictures
    are drawn while the pages are prepared, and `zensical build --clean` then
    empties that directory afterwards - so every diagram was drawn again on the
    next build. Measured on the demo site, where the directory was simply gone
    after a clean build.

    Delete this directory to force every diagram to be drawn again.
    """
    return Path(".zensical-carve") / "diagrams"


class PrerenderError(RuntimeError):
    """Raised when a backend could not produce a picture."""


@dataclass(frozen=True)
class Options:
    """What both seams need to prerender, resolved once."""

    languages: tuple[str, ...] = ()
    url: str = KROKI_URL
    commands: Mapping[str, str] = field(default_factory=dict)
    cache: Path | None = None
    timeout: int = TIMEOUT

    @classmethod
    def from_settings(cls, settings: object) -> "Options | None":
        """Build from a :class:`zensical_carve.config.Settings`, or ``None``.

        ``None`` when nothing is listed, so the caller can skip the pass
        entirely rather than walk the HTML looking for languages nobody asked
        for.
        """
        languages = tuple(getattr(settings, "prerender", ()) or ())
        if not languages:
            return None
        return cls(
            languages=languages,
            url=getattr(settings, "prerender_url", "") or KROKI_URL,
            commands=dict(getattr(settings, "prerender_command", {}) or {}),
            cache=cache_dir(),
            timeout=int(getattr(settings, "prerender_timeout", 0) or TIMEOUT),
        )


def apply(
    markup: str,
    *,
    languages: Sequence[str],
    url: str = KROKI_URL,
    commands: Mapping[str, str] | None = None,
    cache: Path | None = None,
    warn: object = None,
    timeout: int = TIMEOUT,
) -> str:
    """Replace every diagram block in ``languages`` with its picture.

    Args:
        markup: The HTML Carve produced.
        languages: Carve fence words to prerender. Nothing happens to a
            language that is not listed.
        url: A Kroki instance, used for a language with no command.
        commands: Per-language command lines, with ``{input}`` and ``{output}``
            placeholders. A command without ``{output}`` is read from stdout.
        cache: Directory for rendered pictures, or ``None`` to render every
            time.
        warn: Called with a message when one block could not be rendered.

    Returns:
        The HTML, with each rendered block replaced by its SVG.
    """
    wanted = {name for name in languages}
    if not wanted:
        return markup
    commands = dict(commands or {})
    report = warn if callable(warn) else _print_warning

    pieces: list[str] = []
    cursor = 0
    for block in _Finder(wanted).find(markup):
        if block.tag != "pre":
            # The class says diagram and the tag says otherwise, so the engine
            # writes this block in a shape this package does not know how to
            # replace. Saying so is the point: the failure this warning exists
            # for went a month unreported because nothing said anything.
            report(
                f"{block.language}: the engine wrote <{block.tag}"
                f' class="...{block.language}..."> where a <pre> was expected,'
                " so nothing was prerendered"
            )
            continue
        source = html.unescape(markup[block.payload_start : block.payload_end])
        try:
            svg = _render(block.language, source, url, commands, cache, timeout)
        except PrerenderError as error:
            report(f"{block.language}: {error}")
            continue
        pieces.append(markup[cursor : block.start])
        pieces.append(
            f'<div class="carve-diagram carve-diagram-{block.language}">{svg}</div>'
        )
        cursor = block.end

    if not pieces:
        return markup
    pieces.append(markup[cursor:])
    return "".join(pieces)


def _print_warning(message: str) -> None:
    print(f"zensical-carve: could not prerender {message}", file=sys.stderr)


def _render(
    language: str,
    source: str,
    url: str,
    commands: Mapping[str, str],
    cache: Path | None,
    timeout: int = TIMEOUT,
) -> str:
    command = commands.get(language)
    key = _key(language, source, command or f"kroki:{url}")
    if cache is not None:
        cached = _cached(cache / f"{key}.svg")
        if cached is not None:
            return cached

    svg = _clean(
        _command(command, source, timeout)
        if command
        else _kroki(language, source, url, timeout)
    )

    if cache is not None:
        _store(cache / f"{key}.svg", svg)
    return svg


def _cached(path: Path) -> str | None:
    """A usable entry, or ``None`` - a damaged one is a miss, not an error.

    A build interrupted mid-write, a permission change, or a half-copied cache
    directory would otherwise either end the build or put a truncated picture
    on the page, and keep doing it until someone deleted the file by hand.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return text if text.startswith("<svg") and text.rstrip().endswith("</svg>") else None


def _store(path: Path, svg: str) -> None:
    """Write through a temporary file, so a reader never sees half of one."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f"{path.name}.{os.getpid()}.part")
        temporary.write_text(svg, encoding="utf-8")
        temporary.replace(path)
    except OSError:  # pragma: no cover - a read-only project directory
        pass


def _key(language: str, source: str, backend: str) -> str:
    digest = hashlib.sha256()
    for part in (language, backend, source):
        digest.update(part.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:32]


def _kroki(language: str, source: str, url: str, timeout: int = TIMEOUT) -> str:
    endpoint = KROKI_LANGUAGES.get(language)
    if endpoint is None:
        raise PrerenderError(
            f"no Kroki service renders {language}"
            f" (it renders: {', '.join(sorted(KROKI_LANGUAGES))})"
        )
    request = urllib.request.Request(
        f"{url.rstrip('/')}/{endpoint}/svg",
        data=source.encode("utf-8"),
        headers={
            "Content-Type": "text/plain",
            "Accept": "image/svg+xml",
            # The default `Python-urllib/3.x` is turned away by the public
            # instance's bot protection with a 403 that is an HTML page.
            "User-Agent": _USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "replace").strip()
        raise PrerenderError(f"{url} answered {error.code}: {detail[:200]}") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise PrerenderError(f"{url}: {error}") from error

    try:
        return body.decode("utf-8")
    except UnicodeDecodeError as error:
        # An SVG that is not text is not an SVG, and a proxy answering with
        # something binary must not end the build.
        raise PrerenderError(
            f"{url} answered with something that is not text: {error}"
        ) from error


def _command(command: str, source: str, timeout: int = TIMEOUT) -> str:
    try:
        parts = shlex.split(command)
    except ValueError as error:
        raise PrerenderError(f"the command line will not parse: {error}") from error
    if not parts:
        raise PrerenderError("the command is empty")

    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        source_path = directory / "diagram"
        source_path.write_text(source, encoding="utf-8")
        target_path = directory / "diagram.svg"
        wants_file = any("{output}" in part for part in parts)
        argv = [
            part.replace("{input}", str(source_path)).replace(
                "{output}", str(target_path)
            )
            for part in parts
        ]
        try:
            finished = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise PrerenderError(f"{parts[0]}: {error}") from error

        if finished.returncode != 0:
            detail = (finished.stderr or finished.stdout).strip()
            raise PrerenderError(
                f"{parts[0]} exited {finished.returncode}: {detail[:200]}"
            )
        if wants_file:
            try:
                return target_path.read_text(encoding="utf-8")
            except OSError as error:
                raise PrerenderError(f"{parts[0]} wrote no picture: {error}") from error
        if not finished.stdout.strip():
            raise PrerenderError(f"{parts[0]} printed nothing")
        return finished.stdout


def _clean(svg: str) -> str:
    """Make an SVG safe to sit inside a Markdown page.

    The XML prolog and the doctype belong to a standalone file, not to an
    element inside a document. A BLANK LINE is the real hazard: Python-Markdown
    ends a raw HTML block at one, so half the picture would come out as
    paragraph text. Whitespace between tags carries no meaning here, so the
    blank lines go.
    """
    svg = _XML_PROLOG.sub("", svg).strip()
    if not svg.startswith("<svg") and "<svg" in svg:
        svg = svg[svg.index("<svg") :]
    if not svg.startswith("<svg") or not svg.endswith("</svg>"):
        # A backend can fail with a zero exit status: a proxy answering 200
        # with an HTML error page, a binary printing its usage, a truncated
        # response, or an SVG with something appended after it. Putting any of
        # those in place of the block would lose a diagram that still works in
        # the browser.
        raise PrerenderError(f"the backend returned no whole SVG: {svg[:120]!r}")
    return re.sub(r"\n\s*\n", "\n", svg)
