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

from typing import Any, Sequence

__all__ = ["__version__", "CarveError", "fence", "render"]

__version__ = "0.1.0"


class CarveError(RuntimeError):
    """Raised when Carve source cannot be rendered."""


def render(source: str, *, extensions: Sequence[str] | None = None) -> str:
    """Render Carve source to HTML.

    Args:
        source: Carve markup.
        extensions: Optional Carve extension names. An empty sequence and
            ``None`` are different: ``None`` means "use the engine default",
            an empty sequence means "no extensions".

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

    try:
        if extensions is None:
            return carve.to_html(source)
        return carve.to_html_with_extensions(source, list(extensions))
    except Exception as error:
        raise CarveError(f"Carve refused the document: {error}") from error


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
    """
    return render(source)
