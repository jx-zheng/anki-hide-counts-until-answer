#!/usr/bin/env bash
# Build dist/hide_counts_until_answer.ankiaddon.
# manifest.json is at the zip root, which is what Anki installs from.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pkg="$root/hide_counts_until_answer"
out_dir="$root/dist"
out="$out_dir/hide_counts_until_answer.ankiaddon"

if [[ ! -f "$pkg/manifest.json" ]]; then
  echo "missing $pkg/manifest.json" >&2
  exit 1
fi

mkdir -p "$out_dir"
rm -f "$out"
(
  cd "$pkg"
  zip -X -r "$out" . -x '*__pycache__*' '*.pyc' '*.pyo' '*~'
)
echo "Wrote $out"
