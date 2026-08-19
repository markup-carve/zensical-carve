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

A *bold* and /italic/ line, {=highlighted=} text.
```
"""

WHOLE = """\
---
title: A whole Carve page
---

# Whole page mode

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

        whole = (site / "site" / "whole" / "index.html").read_text(encoding="utf-8")
        if "<h1>Whole page mode</h1>" not in whole:
            _fail("the whole page did not render")
        if "<td>carve-rs</td>" not in whole:
            _fail("the Carve table did not survive into the page")
        title = re.search(r"<title>(.*?)</title>", whole, re.S)
        if not title or "A whole Carve page" not in title.group(1):
            _fail("the lifted front matter did not reach the page title")
        if "zensical_carve" in whole:
            _fail("the generated front matter leaked into the body")

    print("e2e: both seams rendered, front matter lifted, title set")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
