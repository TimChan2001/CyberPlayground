#!/usr/bin/env bash
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
