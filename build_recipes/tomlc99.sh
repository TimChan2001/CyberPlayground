#!/usr/bin/env bash
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
OBJ="$SLOT_DIR/toml.o"

clang $SAN -I"$SRC" -c "$SRC/toml.c" -o "$OBJ"
clang $SAN \
    -I"$SRC" \
    "$HARNESS" "$MAIN_C" "$OBJ" \
    -lm -o "$OUT"
