"""Build a real Zensical site through both seams, and assert the Carve came out.

Run directly rather than under pytest: it shells out to `zensical`, takes a
couple of seconds, and is the one check that would notice Zensical changing how
it resolves a custom fence, discovers pages, or strips front matter.

    python tests/e2e_build.py
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

FENCE_LINE = (
    '  { name = "carve", class = "carve", format = "zensical_carve.fence" },'
)

INDEX = """\
# Fence mode

```carve
## Rendered by Carve

A *bold* and /italic/ line, {=highlighted=} text, and a :smile: symbol.

::: details "Only with the extension"
Which the fence can only know from the configuration table.
:::
```
"""

WHOLE = """\
---
title: A whole Carve page
---

# Whole page mode

A :smile: here too.

## A second heading, so the table of contents has something to hold

| Engine | Language |
|--------|----------|
| carve-rs | Rust |
"""


def _fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        site = Path(tmp)
        subprocess.run(["zensical", "new", str(site)], check=True, capture_output=True)

        config_path = site / "zensical.toml"
        config = config_path.read_text(encoding="utf-8")

        anchor = '  { name = "mermaid", class = "mermaid", format = "pymdownx.superfences.fence_code_format" },'
        if anchor not in config:
            _fail("the scaffold no longer carries the mermaid custom fence to anchor on")
        config = config.replace(anchor, anchor + "\n" + FENCE_LINE)
        config = config.replace(
            '  { "Markdown in 5min" = "markdown.md" },',
            '  { "Markdown in 5min" = "markdown.md" },\n'
            '  { "A whole Carve page" = "whole.md" },',
        )
        # Settings both seams read. Zensical ignores a table it does not know,
        # which is what lets them live in its own configuration file.
        config += (
            "\n[tool.zensical-carve]\n"
            'extensions = ["details"]\n'
            'emoji = "twemoji"\n'
        )
        config_path.write_text(config, encoding="utf-8")

        (site / "docs" / "index.md").write_text(INDEX, encoding="utf-8")
        (site / "docs" / "whole.crv").write_text(WHOLE, encoding="utf-8")

        subprocess.run(
            [sys.executable, "-m", "zensical_carve.preprocess", "prepare"],
            cwd=site,
            check=True,
        )
        subprocess.run(["zensical", "build"], cwd=site, check=True, capture_output=True)

        index = (site / "site" / "index.html").read_text(encoding="utf-8")
        if "<strong>bold</strong>" not in index:
            _fail("the fence did not render: Carve strong is missing from index.html")
        if "<mark>highlighted</mark>" not in index:
            _fail("the fence did not render: Carve highlight is missing")
        if "<em>bold</em>" in index:
            _fail("Markdown claimed the block - `*` must be strong in Carve, not emphasis")
        if "<details>" not in index:
            _fail("the fence ignored the extensions in [tool.zensical-carve]")
        if 'class="twemoji"' not in index:
            _fail("the fence ignored the emoji setting in [tool.zensical-carve]")

        whole = (site / "site" / "whole" / "index.html").read_text(encoding="utf-8")
        if "Whole page mode" not in whole:
            _fail("the whole page did not render")
        # The four things a raw-HTML body loses, each measured on a real build
        # before the theme adapter existed.
        anchors = set(re.findall(r'href="(#[^"]+)"', whole))
        if len(anchors) < 2:
            _fail(f"the table of contents is empty: {anchors}")
        if "headerlink" not in whole:
            _fail("headings have no permalink")
        if "<td>carve-rs</td>" not in whole:
            _fail("the Carve table did not survive into the page")
        title = re.search(r"<title>(.*?)</title>", whole, re.S)
        if not title or "A whole Carve page" not in title.group(1):
            _fail("the lifted front matter did not reach the page title")
        if "zensical_carve" in whole:
            _fail("the generated front matter leaked into the body")
        if 'class="twemoji"' not in whole:
            _fail("the whole page ignored the emoji setting")

        # The generated page must say which .crv it came from: Zensical
        # attributes a warning to the file it read, and that is this one.
        generated = (site / "docs" / "whole.md").read_text(encoding="utf-8")
        if 'zensical_carve_source: "docs/whole.crv"' not in generated:
            _fail("the generated page does not record its source")

        # `build` renders the pages here and the fences in a child process.
        # A flag has to reach both, or one page can hold two spellings of the
        # same symbol.
        subprocess.run(
            [sys.executable, "-m", "zensical_carve.preprocess", "build",
             "--force", "--emoji", "unicode"],
            cwd=site,
            check=True,
            capture_output=True,
        )
        index = (site / "site" / "index.html").read_text(encoding="utf-8")
        if "😄" not in index or 'class="twemoji"' in index:
            _fail("`build --emoji unicode` did not reach the fence in the child process")

    print("e2e: both seams rendered, settings honored, front matter lifted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
