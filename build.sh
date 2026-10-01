#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "$0")" && pwd)
KVER=${1:?Usage: ./build.sh <kernel-release>}
[[ "$KVER" =~ ^[[:alnum:].+_-]+$ ]] || { echo "Invalid kernel release string." >&2; exit 2; }
[[ "$(uname -r)" == "$KVER" ]] || { echo "Build only against the running kernel; expected $(uname -r)." >&2; exit 1; }
[[ -d "/lib/modules/$KVER/build" ]] || { echo "Matching kernel headers are missing." >&2; exit 1; }
command -v pahole >/dev/null || { echo "Install pahole (dwarves) for ABI verification." >&2; exit 1; }
"$ROOT/check.sh"
make -C "$ROOT/source" clean KVER="$KVER"
make -C "$ROOT/source" KVER="$KVER"
python3 "$ROOT/source/verify-abi.py" --kver "$KVER"
VERMAGIC=$(modinfo -F vermagic "$ROOT/source/snd-hda-codec-cs8409.ko")
[[ "$VERMAGIC" == "$KVER "* ]] || { echo "Built module vermagic does not match $KVER." >&2; exit 1; }
echo "Build and ABI check finished. The module was not installed or loaded."
