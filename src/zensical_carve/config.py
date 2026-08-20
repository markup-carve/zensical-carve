"""Read plugin settings from the project's own configuration file.

A `.crv` page needs the same extension list on every build, and typing it into
`zensical-carve prepare` each time is how a site ends up rendered two different
ways. Zensical's own configuration is TOML, so the settings live in a TOML
table next to it:

``` toml
[tool.zensical-carve]
extensions = ["details", "tabs", "fenced-render"]
emoji = "twemoji"
```

`zensical.toml` is the first place looked at, because that is where the rest of
the site's configuration is, and Zensical ignores a table it does not know -
measured against 0.0.56, which builds a site with a `[tool.zensical-carve]`
table in its `zensical.toml` without a warning. `pyproject.toml` is read when
`zensical.toml` has no table, for projects that keep tool configuration there.

The table is also what the ```` ```carve ```` fence reads, so a block inside a
Markdown page and a whole `.crv` page render with the same extensions. Before
this existed the fence had no way to enable an extension at all.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised on 3.10 only
    # `tomllib` is 3.11 and later. Zensical itself supports 3.10, so the floor
    # stays where it is and the backport carries it.
    import tomli as tomllib

__all__ = [
    "ConfigError",
    "Settings",
    "encode",
    "find",
    "load",
    "merge",
    "read_symbols",
]

TABLE = ("tool", "zensical-carve")
"""The table read from either file, spelled `[tool.zensical-carve]`."""

FILENAMES = ("zensical.toml", "pyproject.toml")

SETTINGS_ENV = "ZENSICAL_CARVE_SETTINGS"
"""How `build`'s resolved render settings reach the fence.

`zensical-carve build --extension tabs` renders the whole pages itself and then
starts `zensical build`, which renders the ```` ```carve ```` blocks in another
process. Passing the file path alone would lose the flags, so a block and a
page in the same build would come out different. This carries the answer the
flags already produced.
"""

CONFIG_ENV = "ZENSICAL_CARVE_CONFIG"
"""How ``build --config FILE`` reaches the fence.

The fence runs inside `zensical build`, which is a separate process this
package starts. Without the variable it would search the working directory and
could render a block with different settings than the pages beside it.
"""

EMOJI_MODES = ("none", "unicode", "twemoji")


class ConfigError(ValueError):
    """Raised when the configuration table cannot be used as written."""


@dataclass(frozen=True)
class Settings:
    """Everything both entry points need, after file and flags are merged."""

    docs_dir: Path = Path("docs")
    extensions: tuple[str, ...] | None = None
    raw_html: bool = False
    force: bool = False
    emoji: str = "none"
    symbols: dict[str, str] = field(default_factory=dict)
    prerender: tuple[str, ...] = ()
    prerender_url: str = ""
    prerender_command: dict[str, str] = field(default_factory=dict)
    prerender_timeout: int = 0
    source: Path | None = None
    """The file the table came from, or ``None`` when nothing was found."""


def find(start: Path | None = None) -> Path | None:
    """Return the first file that holds the table, or ``None``."""
    base = Path.cwd() if start is None else start
    for name in FILENAMES:
        candidate = base / name
        if candidate.is_file() and _table(candidate) is not None:
            return candidate
    return None


def _table(path: Path) -> Mapping[str, Any] | None:
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except OSError as error:
        raise ConfigError(f"{path}: {error}") from error
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path}: {error}") from error

    node: Any = data
    for key in TABLE:
        if not isinstance(node, Mapping) or key not in node:
            return None
        node = node[key]
    if not isinstance(node, Mapping):
        raise ConfigError(f"{path}: [tool.zensical-carve] is not a table")
    return node


def load(path: Path | None = None, *, start: Path | None = None) -> Settings:
    """Read the table from ``path``, or from the first file that has one.

    An explicit ``path`` that holds no table is an error rather than a silent
    default: it was named on the command line, so it was meant to be used.
    """
    if path is None:
        resolved = os.environ.get(SETTINGS_ENV)
        if resolved:
            return _decode(resolved)
        from_environment = os.environ.get(CONFIG_ENV)
        if from_environment:
            path = Path(from_environment)

    if path is not None:
        table = _table(path)
        if table is None:
            raise ConfigError(f"{path}: no [tool.zensical-carve] table")
        found = path
    else:
        found = find(start)
        if found is None:
            return Settings()
        table = _table(found) or {}

    return _settings(table, found)


_READERS: dict[str, str] = {
    "docs-dir": "docs_dir",
    "extensions": "extensions",
    "raw-html": "raw_html",
    "emoji": "emoji",
    "symbols": "symbols",
    "prerender": "prerender",
    "prerender-url": "prerender_url",
    "prerender-command": "prerender_command",
    "prerender-timeout": "prerender_timeout",
}


def _settings(table: Mapping[str, Any], source: Path) -> Settings:
    values: dict[str, Any] = {"source": source}
    for key, raw in table.items():
        # A TOML author writes `docs-dir`; `docs_dir` is accepted because the
        # Python name is the one visible in this package's own documentation.
        name = _READERS.get(key.replace("_", "-"))
        if name is None:
            known = ", ".join(sorted(_READERS))
            raise ConfigError(
                f"{source}: unknown key '{key}' in [tool.zensical-carve]"
                f" (known keys: {known})"
            )
        values[name] = _value(name, raw, source)
    return Settings(**values)


def _value(name: str, raw: Any, source: Path) -> Any:
    if name == "docs_dir":
        if not isinstance(raw, str):
            raise ConfigError(f"{source}: docs-dir must be a string")
        return Path(raw)

    if name == "extensions":
        if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
            raise ConfigError(f"{source}: extensions must be a list of strings")
        return tuple(raw)

    if name == "raw_html":
        if not isinstance(raw, bool):
            raise ConfigError(f"{source}: raw-html must be true or false")
        return raw

    if name == "emoji":
        if raw not in EMOJI_MODES:
            modes = ", ".join(EMOJI_MODES)
            raise ConfigError(f"{source}: emoji must be one of {modes}")
        return raw

    if name == "symbols":
        return _symbols(raw, source)

    if name == "prerender":
        if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
            raise ConfigError(f"{source}: prerender must be a list of strings")
        return tuple(raw)

    if name == "prerender_url":
        if not isinstance(raw, str):
            raise ConfigError(f"{source}: prerender-url must be a string")
        return raw

    if name == "prerender_timeout":
        if not isinstance(raw, int) or isinstance(raw, bool) or raw <= 0:
            raise ConfigError(f"{source}: prerender-timeout must be seconds, above zero")
        return raw

    if name == "prerender_command":
        if not isinstance(raw, Mapping) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in raw.items()
        ):
            raise ConfigError(
                f"{source}: prerender-command must map a language to a command line"
            )
        return dict(raw)

    raise AssertionError(name)  # pragma: no cover


def _symbols(raw: Any, source: Path) -> dict[str, str]:
    """A symbol map, written inline or kept in a JSON file beside the config.

    The file form exists because a project's own symbols are usually a long
    list, and a long list in the middle of the site configuration hides
    everything after it.
    """
    if isinstance(raw, str):
        path = (source.parent / raw).resolve()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except OSError as error:
            raise ConfigError(f"{source}: symbols file {raw}: {error}") from error
        except json.JSONDecodeError as error:
            raise ConfigError(f"{source}: symbols file {raw}: {error}") from error
    elif isinstance(raw, Mapping):
        data = raw
    else:
        raise ConfigError(f"{source}: symbols must be a table or a path to JSON")

    if not isinstance(data, Mapping) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in data.items()
    ):
        raise ConfigError(f"{source}: symbols must map a name to a string")
    return dict(data)


def encode(settings: Settings) -> str:
    """The render settings, as one string a child process can read back."""
    return json.dumps(
        {
            "extensions": list(settings.extensions)
            if settings.extensions is not None
            else None,
            "emoji": settings.emoji,
            "symbols": settings.symbols,
            "prerender": list(settings.prerender),
            "prerender_url": settings.prerender_url,
            "prerender_command": settings.prerender_command,
            "prerender_timeout": settings.prerender_timeout,
        }
    )


def _decode(raw: str) -> Settings:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ConfigError(f"{SETTINGS_ENV}: {error}") from error
    if not isinstance(data, Mapping):
        raise ConfigError(f"{SETTINGS_ENV}: must hold a JSON object")
    extensions = data.get("extensions")
    return Settings(
        extensions=tuple(extensions) if extensions is not None else None,
        emoji=data.get("emoji", "none"),
        symbols=dict(data.get("symbols") or {}),
        prerender=tuple(data.get("prerender") or ()),
        prerender_url=data.get("prerender_url") or "",
        prerender_command=dict(data.get("prerender_command") or {}),
        prerender_timeout=int(data.get("prerender_timeout") or 0),
    )


def read_symbols(path: Path) -> dict[str, str]:
    """Read a symbol map from a JSON file named on the command line."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ConfigError(f"{path}: {error}") from error
    except json.JSONDecodeError as error:
        raise ConfigError(f"{path}: {error}") from error
    if not isinstance(data, Mapping) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in data.items()
    ):
        raise ConfigError(f"{path}: must be a JSON object mapping a name to a string")
    return dict(data)


def merge(settings: Settings, **overrides: Any) -> Settings:
    """Apply command-line values, where a value of ``None`` means "not given".

    Booleans are the reason this is not a plain ``replace``: a flag that was
    not passed arrives as ``False`` from argparse, which must not turn off what
    the configuration file turned on.
    """
    given = {key: value for key, value in overrides.items() if value not in (None, False)}
    if not given:
        return settings
    return replace(settings, **given)
