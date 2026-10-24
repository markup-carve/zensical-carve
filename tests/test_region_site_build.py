"""Region selection and include warnings in a complete Zensical build."""

from __future__ import annotations

import subprocess
import sys


def test_regions_and_non_text_warning_reach_site(tmp_path):
    docs = tmp_path / "docs"
    (docs / "src").mkdir(parents=True)
    (docs / "src" / "example.py").write_text(
        'outside\n#region demo\nprint("REGION_CODE_OK")\n#endregion\noutside\n',
        encoding="utf-8",
    )
    (docs / "part.crv").write_text(
        "outside\n%% #region name\nREGION_CARVE_OK\n%% #endregion\noutside\n",
        encoding="utf-8",
    )
    (docs / "bad.bin").write_bytes(b"bad\xffbytes")
    (docs / "index.crv").write_text(
        "# Regions\n\n{{ src/example.py @region:demo @code:python }}\n\n"
        "{{ part.crv @region:name }}\n\n{{ bad.bin }}\n",
        encoding="utf-8",
    )
    (tmp_path / "zensical.toml").write_text(
        'site_name = "Regions"\n[tool.zensical-carve]\nincludes = true\n',
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-m", "zensical_carve.preprocess", "build"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    html = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    assert "REGION_CODE_OK" in html
    assert "REGION_CARVE_OK" in html
    assert "outside" not in html
    assert "include-non-text" in result.stderr
