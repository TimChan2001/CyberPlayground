#!/usr/bin/env bash
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
JOBS="${JOBS:-$(nproc)}"

make clean 2>/dev/null || true
make -j"$JOBS" CC=clang CFLAGS="$SAN -fPIC" libgif.a 2>/dev/null

if [ ! -f "$SRC/libgif.a" ]; then
    echo "giflib: libgif.a was not produced" >&2
    exit 1
fi

clang $SAN \
    -I"$SRC" \
    "$HARNESS" "$MAIN_C" "$SRC/libgif.a" \
    -lm -o "$OUT"
