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

`prepare` writes a Markdown page beside each `.crv` whose body is the rendered
HTML. That is not a trick played on Markdown - Python-Markdown passes a
block-level raw HTML through untouched - it is what puts the page into
Zensical's own pipeline, so front matter, navigation, search indexing and the
table of contents all work as they do for any other page.

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
a Carve extension), `--force`.

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

All of them: rendering goes through [`carve-lang`][carve-lang], the PyO3 binding
over the Rust engine, so a page here renders exactly as `carve` on the command
line renders it. Carve extensions are off unless you enable them:

```bash
zensical-carve prepare --extension citations --extension footnotes
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
[zensical-plugins]: https://zensical.org/compatibility/plugins/
