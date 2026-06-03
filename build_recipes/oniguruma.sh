#!/usr/bin/env bash
# Build recipe for oniguruma
set -euo pipefail

cd "$SRC"

autoreconf -fi 2>/dev/null || true
CC=clang CFLAGS="$SAN" ./configure --disable-shared --enable-static 2>/dev/null
make -j"$(nproc)" clean 2>/dev/null || true
make -j"$(nproc)" 2>/dev/null

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"

clang $SAN \
    -I"$SRC/src" \
    "$HARNESS" "$MAIN_C" \
    "$SRC/src/.libs/libonig.a" \
    -o "$OUT"
