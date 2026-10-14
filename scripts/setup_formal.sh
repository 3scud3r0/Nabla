#!/usr/bin/env bash
# Reproduce the tested Linux x86_64 toolchain and build the pinned libraries from source.
set -euo pipefail
repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repository_root"
if [[ $(uname -s) != Linux || $(uname -m) != x86_64 ]]; then
  echo 'This installer targets Linux x86_64. Install the pinned Lean toolchain for your platform and run lake build Nabla NablaMath in lean/.' >&2
  exit 1
fi
tool_root=${NABLA_TOOL_ROOT:-$(dirname "$repository_root")/.tools/lean}
version=4.34.0
archive="$tool_root/lean-$version-linux.tar.zst"
expected_sha256=caaa98356098c85dc0fcbbd28e1ec66f39eb6551829972b752ff20e1286b646b
mkdir -p "$tool_root"
if [[ ! -f "$archive" ]]; then
  curl --fail --location --proto '=https' --tlsv1.2 \
    "https://github.com/leanprover/lean4/releases/download/v$version/lean-$version-linux.tar.zst" \
    --output "$archive"
fi
printf '%s  %s\n' "$expected_sha256" "$archive" | sha256sum --check --status
if [[ ! -x "$tool_root/lean-$version-linux/bin/lean" ]]; then
  tar --zstd -xf "$archive" -C "$tool_root"
fi
export PATH="$tool_root/lean-$version-linux/bin:$PATH"
export MATHLIB_CACHE_DIR="${MATHLIB_CACHE_DIR:-$(dirname "$repository_root")/.cache/mathlib}"
export MATHLIB_NO_CACHE_ON_UPDATE=1
python3 -m venv .venv
PIP_CACHE_DIR="$(dirname "$repository_root")/.cache/pip" .venv/bin/python -m pip install -e '.[test,formal,graphics]'
cd lean
if [[ ! -f lake-manifest.json ]]; then lake update; fi
lake build Nabla NablaMath NablaMath.Examples.FirstProblem
