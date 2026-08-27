# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- The Carve engine dependency remains bounded at `carve-lang>=0.1.1,<0.2.0`;
  release gates are pinned to current 0.1.2 while 0.1.1 remains a valid
  supported floor. On the
  engine's own 0.x scheme `0.1` is the major, so the previous open range admitted
  breaking releases by the engine's own rules.
  markup-carve/zensical-carve#5

### Added

- The engine floor is a checked claim rather than a number:
  `tests/test_engine_floor.py` asserts the resolved engine sanitizes a
  list-valued URL attribute, which is the defect `>=0.1.1` exists for.
  markup-carve/zensical-carve#5

- Diagrams can be drawn at build time instead of in the reader's browser:
  `prerender = ["graphviz", "d2"]` replaces the client-side block with its SVG.
  Rendering goes through a Kroki instance (`prerender-url`) or a local command
  (`prerender-command`), results are cached under `.zensical-carve/diagrams`, and a diagram that
  will not render keeps its block so the page works as before.
- Settings are read from a `[tool.zensical-carve]` table in `zensical.toml`, or
  in `pyproject.toml` when `zensical.toml` has none: `extensions`, `emoji`,
  `symbols`, `docs-dir` and `raw-html`. Flags still win over the file. The
  ` ```carve ` fence reads the same table, so a Carve block and a whole Carve
  page render with the same extensions - the fence had no way to enable one
  before.
- `emoji = "twemoji"` (or `--emoji twemoji`) renders `:smile:` as the same
  `<img class="twemoji">` element a Markdown page on the same site gets, from
  Zensical's own emoji index. `unicode` emits the character instead, `none`
  stays the default. `symbols` adds or overrides individual names.
- `zensical-carve build` passes `--clean` when the Carve settings changed since
  the last build. A rendered page is cached by Zensical's own inputs, and a
  Carve setting is not one of them, so a fenced block kept its old rendering
  after the table changed.
- A generated page records the `.crv` it came from in `zensical_carve_source`,
  because Zensical attributes a warning to the file it read - the generated
  `.md` - and points at a line of HTML the author never wrote.

### Changed

- `convert_tree` returns an `Outcome` (`written`, `skipped`, `failed`) instead
  of a list of paths, so a caller can tell the three apart. The package has not
  been released, so nothing depends on the old shape.

### Fixed

- One page the engine refuses no longer stops the walk, and the message names
  the file. A tree of any size previously reported one message with no path in
  it. A page that is not valid UTF-8 is reported the same way instead of
  raising a decode error with a byte offset and no file name.
- A code block an extension has put markup into stays HTML instead of being
  handed back as a Markdown fence. Code callouts emit `<b class="callout">`
  inside the block, and fencing printed those tags as text.
- Every line of an HTML chunk is left-aligned, not just chunks with a common
  indent. A `<dl>` two sections deep sat at four spaces, which Python-Markdown
  reads as a code block - the glossary rendered as its own open tag in a code
  box. Whitespace inside `<pre>` and `<textarea>` is preserved.

### Added

- Documented which Carve extensions to enable, as three starting-point sets
  (Material parity, diagrams, reference documents), plus the three that collide
  with something Zensical already does. Nothing is enabled for you: which
  extensions a project wants is a project decision, and off-by-default is the
  spec's own rule for Tier-2 and Tier-3.

### Fixed

- Whole `.crv` pages now take part in the theme: the table of contents is
  populated, headings carry permalinks, code blocks get the theme's
  highlighting, copy button and filename bar, and task lists no longer render a
  bullet beside the checkbox. Headings and code blocks are emitted as Markdown
  for Zensical to handle; everything else stays as Carve's HTML. `--raw-html`
  restores the previous behavior.

## [0.1.0]

### Added

- `zensical_carve.fence`, a `pymdownx.superfences` custom fence, so a
  ` ```carve ` block renders inside any Markdown page.
- `zensical-carve prepare` / `build` / `clean`, which render whole `.crv` pages
  to Markdown pages Zensical can build, lifting Carve front matter so `title`
  and the rest reach the page.
- Carve extensions via a repeatable `--extension` flag.
