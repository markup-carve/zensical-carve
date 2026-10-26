# zensical-carve guide

## Background

Use [Carve][carve] in a [Zensical][zensical] site, either as a block inside a
Markdown page or as a complete `.crv` page.

```bash
pip install zensical-carve
```

## Carve blocks in Markdown

Register a `pymdownx.superfences` custom fence in `zensical.toml`:

```toml
pymdownx.superfences.custom_fences = [
  { name = "mermaid", class = "mermaid", format = "pymdownx.superfences.fence_code_format" },
  { name = "carve", class = "carve", format = "zensical_carve.fence" },
]
```

The formatter uses a dot between the module and function. Zensical does not
accept the `module:function` spelling here.

````markdown
```carve

## Rendered by Carve

A *bold* and /italic/ line.
```
````

## Complete Carve pages

Zensical does not discover `.crv` files as pages, so render them before the
site build:

```bash
zensical-carve prepare
zensical build
```

After configuration changes, use the combined command so it passes `--clean`
and avoids stale generated pages:

```bash
zensical-carve build
```

The converter writes a Markdown page beside each source. It returns headings
and code blocks to Zensical as Markdown so the theme can build navigation,
permalinks, syntax highlighting, and code controls. Other constructs remain
Carve HTML to avoid a lossy whole-document Markdown conversion.

Frontmatter is copied to the generated page for Zensical to read.

## Configuration

Settings may live in `[tool.zensical-carve]` inside `zensical.toml` or
`pyproject.toml`:

```toml
[tool.zensical-carve]
extensions = ["details", "tabs", "math-block"]
emoji = "twemoji"
docs-dir = "docs"
```

An extension that takes options is written as an inline table, and
`lint = true` reports lint findings while pages are prepared:

```toml
[tool.zensical-carve]
extensions = ["details", { wikilinks = { css_class = "wiki", new_window = true } }]
lint = true
```

Command-line flags override the file. Configuration also controls symbol maps,
raw HTML, diagram prerendering, and the Kroki endpoint. The default public
Kroki service receives diagram source; use a private endpoint when needed.

## Lint

`zensical-carve lint` reports constructs that parse and render but not the way
the author meant (a block attribute that attaches to nothing, a reference link
with no definition) on every `.crv` page, and exits 1 when it finds any. With
`lint = true` or `--lint`, `prepare` and `build` print the same findings as
warnings, and `zensical-carve build -- --strict` stops before Zensical runs.
With includes on, the linter also checks every included Carve file and names
the include site of each finding there.

## Includes and build output

Includes are off by default. Enable them with `includes = true` or
`--includes`. Carve fences inside
Markdown pages never expand includes. Generated pages record their source and
a generated marker.

## Feature support

Most Carve HTML works directly. Theme-sensitive constructs, diagrams, emoji,
heading links, code blocks, and diff blocks receive specific adapters. See the
[feature matrix](https://github.com/markup-carve/zensical-carve/blob/main/docs/reference.md#which-carve-features-work) and
[collision measurements](https://github.com/markup-carve/zensical-carve/blob/main/docs/reference.md#collisions-with-zensical-measured)
before enabling a large extension set.
