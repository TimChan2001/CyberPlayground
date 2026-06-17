#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/lz4: https://github.com/lz4/lz4 @ release_tag v1.10.0
#   instances/lz4: https://github.com/lz4/lz4.git @ git_commit 1b0fc692949cf474eb0d89db5f0dfa3698e9aa56
# Branch-tip source references are forbidden.
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
JOBS="${JOBS:-$(nproc)}"

make -C lib clean 2>/dev/null || true
make -C lib -j"$JOBS" CC=clang CFLAGS="$SAN -fPIC" liblz4.a 2>/dev/null

if [ ! -f "$SRC/lib/liblz4.a" ]; then
    echo "lz4: lib/liblz4.a was not produced" >&2
    exit 1
fi

clang $SAN \
    -I"$SRC/lib" \
    "$HARNESS" "$MAIN_C" "$SRC/lib/liblz4.a" \
    -lm -o "$OUT"
