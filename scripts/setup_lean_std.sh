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
if [[ ! -f "$archive" ]]; then
  curl --fail --location --proto '=https' --tlsv1.2 \
    "https://github.com/leanprover/lean4/releases/download/v$version/lean-$version-linux.tar.zst" \
    --output "$archive"
fi
printf '%s  %s\n' "$expected_sha256" "$archive" | sha256sum --check --status
if [[ ! -x "$tool_root/lean-$version-linux/bin/lean" ]]; then
  tar --zstd -xf "$archive" -C "$tool_root"
fi
"$tool_root/lean-$version-linux/bin/lean" --version
