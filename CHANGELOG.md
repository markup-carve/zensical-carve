# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0]

### Added

- `zensical_carve.fence`, a `pymdownx.superfences` custom fence, so a
  ` ```carve ` block renders inside any Markdown page.
- `zensical-carve prepare` / `build` / `clean`, which render whole `.crv` pages
  to Markdown pages Zensical can build, lifting Carve front matter so `title`
  and the rest reach the page.
- Carve extensions via a repeatable `--extension` flag.
