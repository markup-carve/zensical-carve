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

### Commands

| command | what it does |
| --- | --- |
| `zensical-carve prepare` | render every `.crv` under `docs/` to a sibling `.md` |
| `zensical-carve build` | `prepare`, then run `zensical build`; extra arguments pass through |
| `zensical-carve clean` | delete the generated pages, and only those |

Options: `--docs-dir` (default `docs`), `--extension NAME` (repeatable, enables
a Carve extension), `--force`, `--raw-html`.

A generated page carries `zensical_carve: generated` in its front matter. That
marker is what `clean` deletes on, and what stops `prepare` from overwriting a
page you wrote by hand - it reports and skips instead, unless you pass
`--force`.

### Two things to know

**Add generated pages to `nav`.** They are ordinary pages, so an explicit `nav`
in `zensical.toml` needs an entry for each one, pointing at the `.md`.

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
is a render option rather than an extension, and **this plugin does not expose it
yet**. Until it does, `:smile:` renders as its own source text. Material ships
twemoji enabled, so this is the one default a migrating project will notice.

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
[zensical-plugins]: https://zensical.org/compatibility/plugins/
