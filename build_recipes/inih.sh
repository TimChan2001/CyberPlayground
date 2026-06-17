#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/inih: https://github.com/benhoyt/inih.git @ git_commit 577ae2dee1f0d9c2d11c7f10375c1715f3d6940c
# Branch-tip source references are forbidden.
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
OBJ="$SLOT_DIR/ini.o"

clang $SAN \
    -DINI_USE_STACK=0 \
    -DINI_ALLOW_REALLOC=1 \
    -I"$SRC" \
    -c "$SRC/ini.c" -o "$OBJ"
clang $SAN \
    -DINI_USE_STACK=0 \
    -DINI_ALLOW_REALLOC=1 \
    -I"$SRC" \
    "$HARNESS" "$MAIN_C" "$OBJ" \
    -o "$OUT"
