"""The package script produces an Anki add-on zip with manifest.json at the root."""

from __future__ import annotations

import stat
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_package_script_builds_ankiaddon(tmp_path: Path) -> None:
    script = ROOT / "scripts" / "package_addon.sh"
    mode = script.stat().st_mode
    assert mode & stat.S_IXUSR
    subprocess.run(["bash", str(script)], check=True, cwd=ROOT)
    archive_path = ROOT / "dist" / "hide_counts_until_answer.ankiaddon"
    assert archive_path.is_file()
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
    assert "manifest.json" in names
    assert "config.json" in names
    assert "config.md" in names
    assert "__init__.py" in names
    assert "allowlist.py" in names
    assert "counts_dom.py" in names
    assert "ui.py" in names
    assert all(not name.startswith("hide_counts_until_answer/") for name in names)
    # The build artifact is gitignored; drop it so the worktree stays clean.
    archive_path.unlink()
