#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "$0")" && pwd)
CC_BIN=${CC:-cc}
TMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/imac-mic-check.XXXXXX")
trap 'rm -rf -- "$TMP_DIR"' EXIT
"$CC_BIN" -std=c11 -Wall -Wextra -Werror -pedantic -O2 \
    "$ROOT/tests/test_capture_route.c" -o "$TMP_DIR/test_capture_route"
"$TMP_DIR/test_capture_route"
if rg -n '\bhdmi_eld\b' "$ROOT/source" -g '*.c' -g '*.h' -g '!hda_local.h'; then
    echo "Unexpected hdmi_eld use; ABI review required." >&2
    exit 1
fi
echo "source checks: PASS"
