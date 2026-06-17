#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/iniparser: https://github.com/ndevilla/iniparser.git @ git_commit 4bef811283e0ec1658c60e09950bd5a1ddc92e4b
# Branch-tip source references are forbidden.
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
OBJ_DIR="$SLOT_DIR/iniparser-objects"
mkdir -p "$OBJ_DIR"

OBJECTS=()
for src in src/dictionary.c src/iniparser.c; do
    obj="$OBJ_DIR/$(basename "${src%.c}").o"
    clang $SAN -I"$SRC/src" -c "$SRC/$src" -o "$obj"
    OBJECTS+=("$obj")
done

clang $SAN \
    -I"$SRC/src" \
    "$HARNESS" "$MAIN_C" "${OBJECTS[@]}" \
    -o "$OUT"
