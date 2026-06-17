#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/heatshrink: https://github.com/atomicobject/heatshrink.git @ git_commit 7d419e1fa4830d0b919b9b6a91fe2fb786cf3280
# Branch-tip source references are forbidden.
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
OBJ_DIR="$SLOT_DIR/heatshrink-objects"
mkdir -p "$OBJ_DIR"

OBJECTS=()
for src in heatshrink_decoder.c heatshrink_encoder.c; do
    obj="$OBJ_DIR/${src%.c}.o"
    clang $SAN -I"$SRC" -c "$SRC/$src" -o "$obj"
    OBJECTS+=("$obj")
done

clang $SAN \
    -I"$SRC" \
    "$HARNESS" "$MAIN_C" "${OBJECTS[@]}" \
    -o "$OUT"
