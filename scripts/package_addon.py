#!/usr/bin/env python3
"""Build dist/hide_counts_until_answer.ankiaddon with manifest.json at the zip root.

Uses the stdlib ``zipfile`` module so the ``zip`` CLI is not required.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

_SKIP_PARTS = {"__pycache__"}
_SKIP_SUFFIXES = {".pyc", ".pyo"}


def build_ankiaddon(repo_root: Path | None = None, dest: Path | None = None) -> Path:
    """Zip the add-on package. Paths inside the archive are relative to the package."""

    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[1]
    package = root / "hide_counts_until_answer"
    if not (package / "manifest.json").is_file():
        raise SystemExit(f"missing {package / 'manifest.json'}")
    archive_path = dest or (root / "dist" / "hide_counts_until_answer.ankiaddon")
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    if archive_path.exists():
        archive_path.unlink()

    files = [
        path
        for path in package.rglob("*")
        if path.is_file()
        and _SKIP_PARTS.isdisjoint(path.parts)
        and path.suffix not in _SKIP_SUFFIXES
        and not path.name.endswith("~")
    ]
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path, path.relative_to(package).as_posix())
    return archive_path


def main() -> None:
    archive_path = build_ankiaddon()
    print(f"Wrote {archive_path}")


if __name__ == "__main__":
    main()
