#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/libconfini: https://github.com/madmurphy/libconfini.git @ git_commit 607241689ff0da8b88bb63fb293dc7efa4770f0d
# Branch-tip source references are forbidden.
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
OBJ="$SLOT_DIR/confini.o"

clang $SAN -D_LIBCONFINI_NOCCWARN_ -I"$SRC/src" -c "$SRC/src/confini.c" -o "$OBJ"
clang $SAN \
    -D_LIBCONFINI_NOCCWARN_ \
    -I"$SRC/src" \
    "$HARNESS" "$MAIN_C" "$OBJ" \
    -o "$OUT"
