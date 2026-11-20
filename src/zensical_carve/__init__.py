"""Carve support for Zensical.

Two entry points, because Zensical offers two seams today and neither is the
module API - that one is not public yet, and its own documentation says so.

``fence``
    A `pymdownx.superfences` custom-fence renderer, so a ```` ```carve ````
    block inside an ordinary Markdown page renders as Carve. This is the
    supported path: Zensical builds pages with Python-Markdown and reads
    ``markdown_extensions`` from ``zensical.toml``.

``render``
    The thin wrapper both seams call, kept public because a project with its
    own macro or template hook may want it directly.

The whole-page path lives in :mod:`zensical_carve.preprocess`: Zensical copies
a non-``.md`` file into the output verbatim, so a ``.crv`` page has to become a
``.md`` page before the build sees it.
"""

from __future__ import annotations

import functools
import os
import sys
from typing import Any, Mapping, Sequence

__all__ = ["__version__", "CarveError", "fence", "lint", "render"]

__version__ = "0.1.7"


class CarveError(RuntimeError):
    """Raised when Carve source cannot be rendered."""


#: The 0.2 standard extensions each 0.1 extension name stands for. A name
#: missing here and not starting with ``carve.`` reaches the engine as written.
LEGACY_EXTENSIONS: dict[str, list[str]] = {
    "autolink": ["carve.autolink"],
    "citations": ["carve.references"],
    "code-callouts": ["carve.codeCallouts"],
    "code-group": ["carve.codeGroup"],
    "color-swatch": ["carve.colorSwatch"],
    "details": ["carve.details"],
    "external-links": ["carve.externalLinks"],
    "fenced-render": ["carve.fencedRender.mermaid"],
    "fenced-render-abc": ["carve.fencedRender.abc"],
    "fenced-render-chart": ["carve.fencedRender.chart"],
    "fenced-render-d2": ["carve.fencedRender.d2"],
    "fenced-render-graphviz": ["carve.fencedRender.graphviz", "carve.fencedRender.dot"],
    "fenced-render-plantuml": ["carve.fencedRender.plantuml", "carve.fencedRender.puml"],
    "fenced-render-vega-lite": ["carve.fencedRender.vega-lite"],
    "fenced-render-wavedrom": ["carve.fencedRender.wavedrom"],
    "glossary": ["carve.glossary"],
    "heading-level-shift": ["carve.headingLevelShift"],
    "heading-numbers": ["carve.headingNumbers"],
    "heading-permalinks": ["carve.headingPermalinks"],
    "heading-reference": ["carve.headingReference"],
    "img-fence": ["carve.imgFence.img", "carve.imgFence.image"],
    "index": ["carve.index"],
    "link-policy": ["carve.linkPolicy"],
    "list-table": ["carve.listTable"],
    "math-block": ["carve.mathBlock"],
    "semantic-span": ["carve.semanticSpan"],
    "smart-quotes": ["carve.smartQuotes"],
    "spoiler": ["carve.spoiler", "carve.spoilerBlock"],
    "tab-normalize": ["carve.tabNormalize"],
    "table-of-contents": ["carve.toc"],
    "tabs": ["carve.tabs"],
    "toc": ["carve.toc"],
    "wikilinks": ["carve.wiki"],
}

#: Standard extensions without a standard renderer in the engine.
_NO_RENDERER = frozenset({"carve.cite"})


def _targets(name: str) -> list[str]:
    """The 0.2 standard extension names one configured ``name`` stands for."""
    if name.startswith("carve."):
        return [name]
    return LEGACY_EXTENSIONS.get(name.replace("_", "-"), [name])


def engine_extensions(names: Sequence[str] | None) -> list[str]:
    """The 0.2 standard extension names for the configured ``names``.

    0.1 names are accepted in either spelling (``math-block``, ``math_block``).
    """
    resolved: list[str] = []
    for name in names or ():
        resolved.extend(t for t in _targets(name) if t not in resolved)
    return resolved


def _entries(
    names: Sequence[str] | None, options: Mapping[str, Mapping[str, Any]] | None
) -> list[Any]:
    """The engine ``extensions`` list: a name, or a configured entry with options.

    Options for a name not in ``names`` are dropped.
    """
    configured: dict[str, dict[str, Any]] = {}
    for name, values in (options or {}).items():
        if values and names and name in names:
            for target in _targets(name):
                configured[target] = dict(values)
    return [
        {"name": n, "options": configured[n]} if n in configured else n
        for n in engine_extensions(names)
    ]


def render(
    source: str,
    *,
    extensions: Sequence[str] | None = None,
    extension_options: Mapping[str, Mapping[str, Any]] | None = None,
    symbols: Mapping[str, str] | None = None,
    include_root: str | None = None,
    source_path: str | None = None,
    warn: "Any | None" = None,
    allow_raw_html: bool = False,
) -> str:
    """Render Carve source to HTML through the Carve 0.2 engine.

    Args:
        source: Carve markup.
        extensions: Optional Carve 0.2 standard extension names, each enabled
            with its standard renderer. A 0.1 name is read as its 0.2
            counterpart (``LEGACY_EXTENSIONS``).
        extension_options: Options per extension name, passed to the engine
            as written. Options for a name not in ``extensions`` are dropped.
        symbols: Optional map from a `:name:` symbol to what it renders as.
            The engine substitutes the value RAW, so a value carrying markup
            reaches the page as markup - which is what the twemoji mode in
            :mod:`zensical_carve.symbols` relies on.
        include_root: The containment root for `{{ path }}` includes, passed to
            the engine as given. Without it, and without ``source_path``, a
            directive stays literal.
        source_path: The document's identity relative to ``include_root``.
        warn: Called with one message per include the engine could not use.
        allow_raw_html: Emit `=html` blocks and spans verbatim. Carve 0.2
            escapes them by default.

    Returns:
        The rendered HTML.

    Raises:
        CarveError: if the engine is missing, or refuses the document.
    """
    try:
        import carve
    except ImportError as error:  # pragma: no cover - exercised by hand
        raise CarveError(
            "the carve-lang package is required to render Carve; "
            "install zensical-carve with its dependencies"
        ) from error

    entries = _entries(extensions, extension_options)
    names = [e if isinstance(e, str) else e["name"] for e in entries]
    options: dict[str, Any] = {}
    if names:
        options["extensions"] = entries
        options["renderers"] = {n: "standard" for n in names if n not in _NO_RENDERER}
    if symbols:
        options["symbols"] = dict(symbols)
    if allow_raw_html:
        options["rawHtml"] = True

    if include_root is None or source_path is None:
        try:
            return carve.render(source, options)["html"]
        except Exception as error:
            raise CarveError(f"Carve refused the document: {error}") from error

    options["includes"] = {"root": include_root, "file": source_path}
    try:
        result = carve.render(source, options, diagnostics=True)
    except Exception as error:
        raise CarveError(f"Carve refused the document: {error}") from error
    if warn is not None:
        _report_includes(result, warn)
    return result["html"]


def lint(
    source: str,
    *,
    extensions: Sequence[str] | None = None,
    include_root: str | None = None,
    source_path: str | None = None,
    caption_hints: bool = False,
) -> list[dict[str, Any]]:
    """The engine's lint findings for one Carve document.

    Each finding is a dict with ``line``, ``column``, ``rule`` and ``message``.
    With ``include_root`` and ``source_path`` the pass also lints every
    included file; such a finding carries the root-relative ``file``. The 0.2
    record has no include chain. ``caption_hints`` is kept for 0.1 callers:
    ``caption-looking-paragraph`` is on by default in Carve 0.2.
    """
    try:
        import carve
    except ImportError as error:  # pragma: no cover - exercised by hand
        raise CarveError("the carve-lang package is required to lint Carve") from error
    options: dict[str, Any] = {}
    names = engine_extensions(extensions)
    if names:
        options["extensions"] = names
    included = include_root is not None and source_path is not None
    if included:
        options["includes"] = {"root": include_root, "file": source_path}
    try:
        diagnostics = carve.lint(source, options)["diagnostics"]
    except Exception as error:
        raise CarveError(f"Carve refused the document: {error}") from error
    findings = []
    for item in diagnostics:
        origin = item.get("file")
        text = source
        if included and origin and origin != source_path:
            with open(os.path.join(include_root, origin), encoding="utf-8") as handle:
                text = handle.read()
        line, column = _position(text, item.get("range", {}).get("startOffset", 0))
        finding = {"line": line, "column": column, "rule": item["code"], "message": item["message"]}
        if origin:
            finding["file"] = origin
        findings.append(finding)
    return findings


def _position(text: str, offset: int) -> tuple[int, int]:
    """A 1-based line and character column for a UTF-8 byte offset in ``text``."""
    before = text.encode("utf-8")[: max(offset, 0)].decode("utf-8", errors="ignore")
    return before.count("\n") + 1, len(before) - (before.rfind("\n") + 1) + 1


def _report_includes(result: Mapping[str, Any], warn: Any) -> None:
    """Hand every degraded include to ``warn``.

    Carve 0.2 reports one code per cause (C2-N-061), so the code already says
    whether the file was missing or refused by containment.
    """
    for warning in result.get("diagnostics", []):
        if not warning["code"].startswith("include-") or warning.get("channel") != "parse":
            continue
        where = warning.get("file")
        location = f"{where}: " if where else ""
        warn(f"{location}{warning['code']}: {warning['message']}")
    suppressed = result.get("suppressedDiagnostics", 0)
    if suppressed:
        warn(f"{suppressed} further include warnings suppressed")


def fence(
    source: str,
    language: str,
    css_class: str,
    options: dict[str, Any],
    md: Any,
    **kwargs: Any,
) -> str:
    """Render a ```` ```carve ```` block, as a superfences custom fence.

    The signature is the one `pymdownx.superfences` calls with; every argument
    but ``source`` is accepted and ignored, because a Carve document decides
    its own structure and has nothing to take from the fence line.

    Register it in ``zensical.toml``::

        pymdownx.superfences.custom_fences = [
          { name = "carve", class = "carve", format = "zensical_carve.fence" },
        ]

    Note the DOT before ``fence``. Zensical resolves these symbols with
    ``rsplit(".", 1)``, so the ``module:function`` spelling that works in some
    other tools raises a ``ValueError`` during config parsing here.

    Extensions and symbols come from the ``[tool.zensical-carve]`` table, the
    same one the whole-page path reads, so a block and a page render alike.
    There is nowhere else they could come from: superfences hands a fence its
    own options, and the fence line of a Carve block carries none.

    Includes are read from that table too, and then not applied: a fence has no
    file of its own for a relative path to resolve against. The one thing that
    must not happen is applying them silently under some other identity, so the
    block keeps its directive literal and the build says once that it did.
    """
    settings, symbol_map, prerender_options = _runtime()
    if settings.includes:
        _note_fence_includes()
    html = render(
        source,
        extensions=settings.extensions,
        extension_options=settings.extension_options,
        symbols=symbol_map,
        allow_raw_html=settings.allow_raw_html,
    )
    if prerender_options is not None:
        from . import prerender

        html = prerender.apply(
            html,
            languages=prerender_options.languages,
            url=prerender_options.url,
            commands=prerender_options.commands,
            cache=prerender_options.cache,
            timeout=prerender_options.timeout,
        )
    return html


@functools.lru_cache(maxsize=1)
def _note_fence_includes() -> None:
    """Said once per process, not once per block."""
    print(
        "zensical-carve: a carve fence has no source file, so `{{ path }}`"
        " stays literal inside one; whole pages still expand",
        file=sys.stderr,
    )


@functools.lru_cache(maxsize=1)
def _runtime() -> tuple[
    "config.Settings", Mapping[str, str] | None, "prerender.Options | None"
]:
    """The configuration table and its symbol map, built once per process.

    A build calls the fence for every Carve block on every page, and the emoji
    map is twenty thousand entries, so neither is rebuilt per call. The file
    cannot change underneath a build - Zensical has already parsed the same
    file to know the fence exists.
    """
    from . import config, prerender, symbols as symbol_module

    try:
        settings = config.load()
    except config.ConfigError as error:
        raise CarveError(str(error)) from error
    options = prerender.Options.from_settings(settings)
    if options is not None:
        # A warning rather than a refusal: this runs inside `zensical build`,
        # where raising would take the whole site down over a spelling.
        unknown = prerender.unsupported(options)
        if unknown:
            print(
                f"zensical-carve: nothing renders {', '.join(unknown)} -"
                " those blocks stay client-side",
                file=sys.stderr,
            )
    return settings, symbol_module.build(settings.emoji, settings.symbols), options
