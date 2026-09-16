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
import sys
from typing import Any, Mapping, Sequence

__all__ = ["__version__", "CarveError", "fence", "render"]

__version__ = "0.1.0"


class CarveError(RuntimeError):
    """Raised when Carve source cannot be rendered."""


def render(
    source: str,
    *,
    extensions: Sequence[str] | None = None,
    symbols: Mapping[str, str] | None = None,
    include_root: str | None = None,
    source_path: str | None = None,
    warn: "Any | None" = None,
) -> str:
    """Render Carve source to HTML.

    Args:
        source: Carve markup.
        extensions: Optional Carve extension names. An empty sequence and
            ``None`` are different: ``None`` means "use the engine default",
            an empty sequence means "no extensions".
        symbols: Optional map from a `:name:` symbol to what it renders as.
            The engine substitutes the value RAW, so a value carrying markup
            reaches the page as markup - which is what the twemoji mode in
            :mod:`zensical_carve.symbols` relies on.
        include_root: The containment root for `{{ path }}` includes, passed to
            the engine as given. Without it, and without ``source_path``, a
            directive stays literal.
        source_path: The document's identity relative to ``include_root``.
        warn: Called with one message per include the engine could not use.

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

    options: dict[str, Any] = {}
    if extensions is not None:
        options["extensions"] = list(extensions)
    if symbols:
        options["symbols"] = dict(symbols)

    if include_root is None or source_path is None:
        try:
            return carve.to_html(source, **options)
        except Exception as error:
            raise CarveError(f"Carve refused the document: {error}") from error

    if not hasattr(carve, "render_with_includes"):
        raise CarveError(
            "the installed carve-lang exposes no render_with_includes;"
            " upgrade the engine, or turn includes off"
        )
    try:
        result = carve.render_with_includes(
            source, include_root, source_path=source_path, **options
        )
    except Exception as error:
        raise CarveError(f"Carve refused the document: {error}") from error
    if warn is not None:
        _report_includes(result, warn)
    return result["output"]


def _report_includes(result: Mapping[str, Any], warn: Any) -> None:
    """Hand every degraded include to ``warn``, with its class where there is one.

    The engine reports a containment refusal and a missing file as the same
    `include-unresolved` warning, so a page cannot probe the filesystem (spec
    I7). Which one it was is on the dependency, and that is where this reads it
    from - the sanitized warning is left as the engine wrote it.
    """
    denials = {
        dependency["id"]: dependency["denial"]
        for dependency in result["dependencies"]
        if dependency["denial"]
    }
    for warning in result["warnings"]:
        where = warning.get("file")
        location = f"{where}: " if where else ""
        warn(f"{location}{warning['rule']}: {warning['message']}")
    suppressed = result["suppressed_warnings"]
    if suppressed:
        warn(f"{suppressed} further include warnings suppressed")
    for identifier, denial in denials.items():
        warn(f"include {identifier}: {denial}")


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
    html = render(source, extensions=settings.extensions, symbols=symbol_map)
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
