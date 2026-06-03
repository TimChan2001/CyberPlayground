#!/usr/bin/env bash
# Build recipe for lua
set -euo pipefail

cd "$SRC"

make clean 2>/dev/null || true
make -j"$(nproc)" \
    CC=clang \
    CFLAGS="$SAN -DLUA_USE_POSIX" \
    MYLIBS="-lm" \
    liblua.a 2>/dev/null

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"

clang $SAN \
    -I"$SRC" \
    "$HARNESS" "$MAIN_C" \
    "$SRC/liblua.a" \
    -lm \
    -o "$OUT"
