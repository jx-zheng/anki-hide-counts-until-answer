#!/usr/bin/env bash
# Build dist/hide_counts_until_answer.ankiaddon.
# manifest.json is at the zip root, which is what Anki installs from.
# The archive is written with Python's zipfile module, not the zip CLI.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$root/scripts/package_addon.py"
