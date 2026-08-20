# zensical-carve

Write [Carve][carve] in a [Zensical][zensical] site - a whole page, or a block
inside a Markdown page.

Zensical is the successor to MkDocs and Material for MkDocs, from the same team.

```bash
pip install zensical-carve
```

## A Carve block inside a Markdown page

Zensical renders pages with Python-Markdown and reads `markdown_extensions` from
`zensical.toml`, so a Carve block is a `pymdownx.superfences` custom fence:

```toml
pymdownx.superfences.custom_fences = [
  { name = "mermaid", class = "mermaid", format = "pymdownx.superfences.fence_code_format" },
  { name = "carve", class = "carve", format = "zensical_carve.fence" },
]
```

Then anywhere in a `.md` page:

````markdown
Ordinary Markdown here.

```carve
## Rendered by Carve

A *bold* and /italic/ line, {=highlighted=} text, and a `code` span.
```
````

Note the **dot** in `zensical_carve.fence`. Zensical resolves these symbols with
`rsplit(".", 1)`, so the `module:function` spelling that other tools accept
fails during config parsing with `ValueError: not enough values to unpack`.

## A whole `.crv` page

Zensical discovers pages by extension, and a `.crv` file is not a page - it is
copied into the output as a static file. So a whole Carve page is rendered
before the build:

```bash
zensical-carve prepare      # docs/**/*.crv  ->  docs/**/*.md
zensical build
```

or in one step:

```bash
zensical-carve build
```

`prepare` writes a Markdown page beside each `.crv`. Most of the body is the
rendered HTML - Python-Markdown passes a block-level raw HTML through untouched
- but **headings and code blocks are handed back to Zensical as Markdown**, and
that part is not cosmetic. A page whose body is HTML all the way down builds
fine and then behaves wrong:

| | body is all HTML | headings and code handed back |
| --- | --- | --- |
| table of contents | empty | complete |
| heading permalinks | none | on every heading |
| code syntax colors, copy button | none | the theme's own |
| code block title | invisible `title=` attribute | the theme's filename bar |
| task lists | bullet *and* checkbox | the theme's checkbox |

Everything else stays as Carve's HTML, deliberately. Carve can render a whole
page to Markdown, but lossily - an admonition comes out as a bold paragraph
with the container gone - so converting the whole page would trade this set of
flaws for a worse one. Admonitions, definition lists, tables with captions and
every inline mark keep their fidelity.

Pass `--raw-html` if you want the unadapted HTML anyway.

Carve front matter is lifted rather than rendered:

```
---
title: A whole Carve page
---

# Whole page mode
```

becomes a page whose `title` Zensical reads, exactly as if you had written the
front matter in Markdown.

### Configuration

Every setting can live in a `[tool.zensical-carve]` table instead of on the
command line, so a site renders the same way on every build and in CI:

``` toml
[tool.zensical-carve]
extensions = ["details", "tabs", "fenced-render", "math-block", "semantic-span"]
emoji = "twemoji"
docs-dir = "docs"
```

`zensical.toml` is read first - Zensical ignores a table it does not know, so
the Carve settings sit next to the rest of the site's configuration - and
`pyproject.toml` is read when `zensical.toml` has no table. A flag beats the
file, so `--extension` on the command line replaces the configured list for
that one run. `--config FILE` points at a file directly.

| key | what it takes |
| --- | --- |
| `extensions` | list of Carve extension names |
| `emoji` | `none` (default), `unicode`, or `twemoji` |
| `symbols` | inline table, or a path to a JSON object, mapping a name to what `:name:` renders as |
| `docs-dir` | the directory to walk, default `docs` |
| `raw-html` | `true` to skip the theme adaptation |
| `prerender` | list of diagram languages to draw at build time |
| `prerender-url` | a Kroki instance, default `https://kroki.io` |
| `prerender-command` | per-language command line, for a local binary |
| `prerender-timeout` | seconds one diagram may take, default 60 |

**Changing a setting cleans Zensical's cache.** A rendered page is cached by
Zensical's own inputs, and a Carve setting is not one of them - switching
`emoji` and rebuilding served the old page again, measured on 0.0.56. So
`zensical-carve build` records what it rendered with and passes `--clean` when
that changes. Running `zensical build` yourself does not: clean it by hand
after changing the table, or use `zensical-carve build`.

**The fence reads this table too.** A ` ```carve ` block inside a Markdown page
had no way to enable an extension before - superfences hands a fence its own
options, and a Carve fence line carries none. Now a block and a whole page
render alike.

### Commands

| command | what it does |
| --- | --- |
| `zensical-carve prepare` | render every `.crv` under `docs/` to a sibling `.md` |
| `zensical-carve build` | `prepare`, then run `zensical build`; extra arguments pass through |
| `zensical-carve clean` | delete the generated pages, and only those |

Options: `--docs-dir` (default `docs`), `--config FILE`, `--extension NAME`
(repeatable, enables a Carve extension), `--emoji none|unicode|twemoji`,
`--symbols FILE.json`, `--prerender LANGUAGE` (repeatable), `--prerender-url
URL`, `--force`, `--raw-html`. Each has a key in the
configuration table above.

A generated page carries `zensical_carve: generated` in its front matter. That
marker is what `clean` deletes on, and what stops `prepare` from overwriting a
page you wrote by hand - it reports and skips instead, unless you pass
`--force`.

### Two things to know

**Add generated pages to `nav`.** They are ordinary pages, so an explicit `nav`
in `zensical.toml` needs an entry for each one, pointing at the `.md`.

**A build warning names the generated page, not your source.** Zensical
validates links against the file it read, so a broken link written in
`page.crv` is reported at `page.md:7:15` - a line of HTML you never wrote.
Every generated page carries `zensical_carve_source` in its front matter, which
is the one hop back. This is Zensical's [backlog#109][backlog-109], and it goes
away when errors are attributed to input files.

**The `.crv` file is copied into the built site too.** Zensical treats any
non-page file in `docs/` as a static asset and has no `exclude` setting as of
0.0.56. It is harmless, and shipping the source next to the page is arguably a
feature; if you would rather not, keep your `.crv` files outside `docs/` and
point `--docs-dir` at a staging copy.

## Which Carve features work

Core Carve works out of the box: rendering goes through [`carve-lang`][carve-lang],
the PyO3 binding over the Rust engine, so a page here renders exactly as `carve`
on the command line renders it.

Carve's Tier-2 and Tier-3 extensions are **off unless you enable them**, which is
the spec's own default and not a choice this plugin makes. Which ones you want is
a project question, so nothing is turned on for you:

```bash
zensical-carve prepare --extension fenced-render --extension details
```

`carve.extensions()` lists all 32 names. The sets below are starting points.

### The Material-parity set

What a project migrating from Material for MkDocs will expect to keep working,
because Material has the equivalent on by default:

```bash
--extension fenced-render --extension details --extension tabs \
--extension math-block --extension semantic-span
```

| you had | enable | note |
| --- | --- | --- |
| `pymdownx.superfences` mermaid | `fenced-render` | see the collision table |
| `pymdownx.details` | `details` | renders `<details><summary>` |
| `pymdownx.tabbed` | `tabs` | see the collision table |
| `pymdownx.arithmatex` | `math-block` | |
| `pymdownx.keys` | *nothing yet* | markup-carve/carve#1441 |

Everything else Material gives you is already core Carve and needs no flag:
admonitions, task lists, footnotes, definition lists, abbreviations, attributes,
highlight, strikethrough, superscript and subscript, and includes.

### The diagrams set

Carve draws eight diagram languages, each a `FencedRender` preset. `d2` is
included - the language Zensical tracks as a change request in
zensical/backlog#29:

```bash
--extension fenced-render --extension fenced-render-d2 \
--extension fenced-render-graphviz --extension fenced-render-plantuml \
--extension fenced-render-vega-lite --extension fenced-render-wavedrom \
--extension fenced-render-chart --extension fenced-render-abc
```

`fenced-render` alone covers ` ```mermaid `. The others each claim their own
fence word.

### Diagrams at build time

Carve's diagram fences emit the block a client-side library picks up, so the
reader downloads Mermaid, sees the source for a moment, and watches the page
shift when the picture replaces it. Listing a language draws it during the
build instead:

``` toml
[tool.zensical-carve]
extensions = ["fenced-render", "fenced-render-graphviz", "fenced-render-d2"]
prerender = ["graphviz", "d2"]
```

`<pre class="graphviz">` becomes `<div class="carve-diagram carve-diagram-graphviz">`
with the SVG inside it. Nothing else on the page changes, and a language you do
not list is left for the browser exactly as before.

Two backends. By default the source is POSTed to [Kroki][kroki], which speaks
`mermaid`, `d2`, `graphviz`, `plantuml`, `wavedrom` and `vega-lite`. **That
sends the diagram off the machine**, so point `prerender-url` at your own
instance for anything not public. Or render locally, and nothing leaves at all:

``` toml
[tool.zensical-carve.prerender-command]
mermaid = "mmdc -i {input} -o {output}"
graphviz = "dot -Tsvg {input}"
```

`{input}` is the diagram source in a temporary file, `{output}` is where the
picture should go; a command without `{output}` is read from its standard
output. A command beats Kroki for that language.

Rendered pictures are cached under `.zensical-carve/diagrams`, keyed by the
source and the backend, so a second build draws nothing again. Add that
directory to `.gitignore`, and delete it to force a redraw. It sits outside
Zensical's own `.cache` on purpose: diagrams are drawn while the pages are
prepared, and `zensical build --clean` empties `.cache` after that, which threw
away every picture that had just been drawn.

**A diagram that will not render leaves its block alone**, warns, and names the
page - the client-side library then picks it up the way it did before. Two
things worth knowing before you turn this on: the public Kroki instance renders
graphviz in under a second but runs a headless browser for mermaid, which timed
out at 30 seconds during this work (hence the 60 second default and
`prerender-timeout`); and a graphviz SVG carries `fill="white"`, so it wants a
CSS rule of yours in dark mode.

`chart` and `abc` have no Kroki service. Give them a command or leave them
client-side - listing one without a command is an error rather than a silent
skip.

### The reference-document set

For handbooks and specifications rather than product docs:

```bash
--extension citations --extension glossary --extension index \
--extension heading-numbers --extension list-table --extension wikilinks \
--extension heading-reference --extension code-callouts
```

### Collisions with Zensical, measured

Three extensions do something Zensical already does, so enabling them duplicates
rather than adds:

| extension | what happens | verdict |
| --- | --- | --- |
| `heading-permalinks` | Carve adds a `¶` anchor, and Zensical's `toc.permalink` already added one | **do not enable** - you get two |
| `toc` / `table-of-contents` | renders a `<nav>` into the page body; the theme's sidebar table of contents is separate and already populated | enable only if you want a second, in-body one |
| `tabs` | emits `<div class="tabs">` with radio inputs and Carve's own class names, which Material's tab CSS does not style | works, needs your own CSS |

And one that lines up better than expected: ` ```mermaid ` under `fenced-render`
emits `<pre class="mermaid">`, which is what Zensical's own mermaid fence emits
too (one element shallower - Zensical wraps the payload in `<code>`). So a site
that already has mermaid running picks up Carve's mermaid blocks with no extra
configuration.

### Emoji is not an extension

`:smile:` parsing is core and on by default, but the map from a name to a glyph
is a render option rather than an extension, so a document that reaches the
engine without one renders `:smile:` as its own source text. Set `emoji`:

``` toml
[tool.zensical-carve]
emoji = "twemoji"
```

`twemoji` emits the same `<img class="twemoji">` element Zensical emits for a
Markdown page, from Zensical's own emoji index and pointing at the same CDN, so
the two page types look identical and the theme's sizing applies. `unicode`
emits the character itself - no network, no images, and it inherits the page's
font, which on Linux is often no color emoji font at all.

Names that resolve to an icon rather than an emoji (`:material-home:` and its
ten thousand siblings) are not in the map: they are SVG files on disk, and
reading them all to build one map costs more than the feature is worth. Add the
ones you use through `symbols`, which takes anything - the engine substitutes a
symbol raw, markup included:

``` toml
[tool.zensical-carve.symbols]
crab = "🦀"
shipped = "<span class=\"badge\">shipped</span>"
```

## Why there is no Zensical module

Zensical's module system is the eventual home for this, and its API is not
public yet - the project [says so][zensical-plugins]: *"we are currently holding
back on releasing a public API"*. Both seams used here are the supported public
ones today, and the package is shaped so the module can replace the plumbing
without changing how you write a page.

## Related

- [carve][carve] - the language
- [carve-lang][carve-lang] - the Python binding this package renders with
- [mkdocs-carve](https://github.com/markup-carve/mkdocs-carve) - the same idea for MkDocs

## License

MIT

[carve]: https://markup-carve.github.io/carve/
[carve-lang]: https://pypi.org/project/carve-lang/
[zensical]: https://zensical.org/
[kroki]: https://kroki.io/
[zensical-plugins]: https://zensical.org/compatibility/plugins/
[backlog-109]: https://github.com/zensical/backlog/issues/109
