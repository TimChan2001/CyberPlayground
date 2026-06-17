#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/json_parser: https://github.com/udp/json-parser.git @ git_commit 8ac4477ad3e63dc107e17ad49484edaa17d18d35
# Branch-tip source references are forbidden.
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
OBJ="$SLOT_DIR/json_parser.o"

clang $SAN -I"$SRC" -c "$SRC/json.c" -o "$OBJ"
clang $SAN \
    -I"$SRC" \
    "$HARNESS" "$MAIN_C" "$OBJ" \
    -lm -o "$OUT"
