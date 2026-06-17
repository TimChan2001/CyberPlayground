#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/yyjson: https://github.com/ibireme/yyjson.git @ git_commit f0fbeae7cc40218fd1af310391cdf83cfc1abff1
# Branch-tip source references are forbidden.
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
OBJ="$SLOT_DIR/yyjson.o"

clang $SAN -I"$SRC/src" -c "$SRC/src/yyjson.c" -o "$OBJ"
clang $SAN \
    -I"$SRC/src" \
    "$HARNESS" "$MAIN_C" "$OBJ" \
    -o "$OUT"
