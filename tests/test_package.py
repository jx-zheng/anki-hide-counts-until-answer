"""The package script produces an Anki add-on zip with manifest.json at the root."""

from __future__ import annotations

import stat
import zipfile
from pathlib import Path

from scripts.package_addon import build_ankiaddon

ROOT = Path(__file__).resolve().parents[1]


def test_package_script_builds_ankiaddon_without_zip_cli(tmp_path: Path) -> None:
    script = ROOT / "scripts" / "package_addon.sh"
    assert script.stat().st_mode & stat.S_IXUSR
    source = script.read_text()
    assert "package_addon.py" in source
    assert "\nzip " not in source
    assert not source.lstrip().startswith("zip ")

    archive_path = build_ankiaddon(ROOT, tmp_path / "hide_counts_until_answer.ankiaddon")
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
