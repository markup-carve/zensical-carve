# Releasing

`zensical-carve` publishes to PyPI from `.github/workflows/release.yml`, which
runs on a pushed bare SemVer tag (`X.Y.Z`).

## Publishing setup

The `zensical-carve` project already exists on PyPI. Keep the repository's
`pypi` environment and trusted publisher aligned with `release.yml`. An API
token is only a fallback when trusted publishing is unavailable.

1. In the repository settings, create an environment named `pypi`. The publish
   job is bound to it, so restricting who may approve it also restricts who may
   release.
2. On PyPI, configure the trusted publisher for owner `markup-carve`, repository
   `zensical-carve`, workflow `release.yml`, and environment `pypi`.

## Per release

1. Move the entries under a version heading in `CHANGELOG.md` and set its date.
2. Set the version in **both** places: `project.version` in `pyproject.toml` and
   `__version__` in `src/zensical_carve/__init__.py`. They feed different
   readers - PyPI and `pip show` report the first, anything importing the
   package reads the second - and the workflow refuses a tag that disagrees with
   either. carve-js shipped an exported constant reading 0.1.0 across three
   releases because only one of its two places was bumped
   (`markup-carve/carve-js#1074`).
3. Create a draft GitHub release for `X.Y.Z` and write its release notes.
4. Tag `X.Y.Z` and push the tag. The workflow requires a bare SemVer tag such
   as `0.1.0`; it uploads the artifacts and publishes the prepared draft.

## What runs before anything is uploaded

- the tag matches both version strings
- a draft release with non-empty notes exists for the tag
- no direct-URL dependency survives, which PyPI would refuse anyway
- `twine check --strict` on the built distributions
- **the gate**: the built wheel is installed into a clean virtualenv, the import
  is confirmed to resolve into `site-packages` rather than the checkout, and a
  real Zensical site is built through both seams with it

The gate is the only one of those that asks whether the artifact works. The
others are paperwork - a module left out of the wheel passes every test in the
checkout and fails the gate. `publish` needs it, so an upload is unreachable
while it is red.

## Exercising the path without spending a tag

`workflow_dispatch` runs build and gate and stops there, because `publish` is
guarded on a tag ref. Use it after changing anything in the release path:

```bash
gh workflow run release.yml --ref <branch>
```
