#!/usr/bin/env bash
# Prepare the pinned Mathlib closure once, before running bounded proof checks.
set -euo pipefail
repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repository_root"
bash scripts/setup_lean_std.sh
tool_root=${NABLA_TOOL_ROOT:-$(dirname "$repository_root")/.tools/lean}
export PATH="$tool_root/lean-4.34.0-linux/bin:$PATH"
export MATHLIB_CACHE_DIR="${MATHLIB_CACHE_DIR:-$repository_root/.nabla/mathlib-cache}"
export MATHLIB_NO_CACHE_ON_UPDATE=1
mkdir -p .nabla
# Concurrent setup must never replace an environment under an active setup.
exec 9>.nabla/formal-setup.lock
flock -n 9 || { echo 'Another formal setup is running.' >&2; exit 1; }
if [[ ! -x .venv/bin/python ]]; then python3 -m venv .venv; fi
.venv/bin/python -m pip install -e '.[test,formal,graphics]'
# The checked-in manifest is mandatory. Never run an unpinned lake update.
manifest_before=$(sha256sum lean/lake-manifest.json)
cd lean
case "${NABLA_FORMAL_CACHE:-download}" in
  download)
    lake exe cache get Mathlib.Tactic.Ring Mathlib.Tactic.FieldSimp \
      Mathlib.Tactic.Linarith Mathlib.Tactic.NormNum Mathlib.Data.Rat.Defs ;;
  source) ;; # Explicit slower fallback, preserving the same pinned sources.
  *) echo 'NABLA_FORMAL_CACHE must be download or source' >&2; exit 1 ;;
esac
cd "$repository_root"
[[ $(sha256sum lean/lake-manifest.json) == "$manifest_before" ]] || {
  echo 'Pinned Lake manifest changed during setup; refusing build.' >&2; exit 1;
}
.venv/bin/python tools/check_formal_environment.py --sources-only
cd lean
lake build Nabla NablaMath NablaMath.Examples.FirstProblem
cd "$repository_root"
.venv/bin/python tools/check_formal_environment.py
