# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
