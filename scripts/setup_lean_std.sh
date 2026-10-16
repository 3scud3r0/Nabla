#!/usr/bin/env bash
# Install the pinned official Lean distribution without building Mathlib.
set -euo pipefail
repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
if [[ $(uname -s) != Linux || $(uname -m) != x86_64 ]]; then
  echo 'This recipe requires Linux x86_64; install the pinned official toolchain for your platform.' >&2
  exit 1
fi
version=4.34.0
if [[ $(cat "$repository_root/lean/lean-toolchain") != "leanprover/lean4:v$version" ]]; then
  echo 'Toolchain pin changed; obtain its official checksum before updating this installer.' >&2
  exit 1
fi
tool_root=${NABLA_TOOL_ROOT:-$(dirname "$repository_root")/.tools/lean}
archive="$tool_root/lean-$version-linux.tar.zst"
expected_sha256=caaa98356098c85dc0fcbbd28e1ec66f39eb6551829972b752ff20e1286b646b
mkdir -p "$tool_root"
exec 8>"$tool_root/.setup.lock"
flock -n 8 || { echo 'Another pinned Lean installation is running.' >&2; exit 1; }
download_path=''
extract_path=''
cleanup() {
  if [[ -n "$download_path" ]]; then rm -f -- "$download_path"; fi
  if [[ -n "$extract_path" ]]; then rm -rf -- "$extract_path"; fi
}
trap cleanup EXIT
if [[ ! -f "$archive" ]]; then
  download_path=$(mktemp "$tool_root/.lean-download.XXXXXX")
  curl --fail --location --proto '=https' --tlsv1.2 \
    "https://github.com/leanprover/lean4/releases/download/v$version/lean-$version-linux.tar.zst" \
    --output "$download_path"
  printf '%s  %s\n' "$expected_sha256" "$download_path" | sha256sum --check --status
  mv -- "$download_path" "$archive"
  download_path=''
fi
printf '%s  %s\n' "$expected_sha256" "$archive" | sha256sum --check --status
if [[ ! -x "$tool_root/lean-$version-linux/bin/lean" ]]; then
  if [[ -e "$tool_root/lean-$version-linux" ]]; then
    echo 'Incomplete toolchain directory; preserve/rename it before reinstalling.' >&2
    exit 1
  fi
  extract_path=$(mktemp -d "$tool_root/.lean-extract.XXXXXX")
  tar --zstd -xf "$archive" -C "$extract_path"
  mv -- "$extract_path/lean-$version-linux" "$tool_root/lean-$version-linux"
fi
"$tool_root/lean-$version-linux/bin/lean" --version
