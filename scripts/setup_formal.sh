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
bash "$repository_root/scripts/setup_lean_std.sh"
export PATH="$tool_root/lean-4.34.0-linux/bin:$PATH"
export MATHLIB_CACHE_DIR="${MATHLIB_CACHE_DIR:-$(dirname "$repository_root")/.cache/mathlib}"
export MATHLIB_NO_CACHE_ON_UPDATE=1
python3 -m venv .venv
PIP_CACHE_DIR="$(dirname "$repository_root")/.cache/pip" .venv/bin/python -m pip install -e '.[test,formal,graphics]'
.venv/bin/python tools/setup_formal_dependencies.py
cd lean
# Fail once on a denied destination instead of attempting thousands of downloads.
curl --silent --show-error --head --max-time 20 --output /dev/null https://cache.mathlib.org/
lake exe cache get
lake build Nabla NablaMath NablaMath.Examples.FirstProblem
