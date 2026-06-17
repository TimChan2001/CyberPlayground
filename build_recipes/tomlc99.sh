#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/tomlc99: https://github.com/cktan/tomlc99.git @ git_commit 29076dfd095bbbbd50a3c1b2760d29f4b83e74ac
#   instances/tomlc99: https://github.com/cktan/tomlc99.git @ git_commit 29076dfd095bbbbd50a3c1b2760d29f4b83e74ac
# Branch-tip source references are forbidden.
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
