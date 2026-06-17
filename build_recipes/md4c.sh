#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/md4c: https://github.com/mity/md4c.git @ git_commit 81b871f917ec97b94322f3890fc12f0657ed3d94
# Branch-tip source references are forbidden.
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
OBJ_DIR="$SLOT_DIR/md4c-objects"
mkdir -p "$OBJ_DIR"

OBJECTS=()
for src in src/entity.c src/md4c.c; do
    obj="$OBJ_DIR/$(basename "${src%.c}").o"
    clang $SAN -I"$SRC/src" -c "$SRC/$src" -o "$obj"
    OBJECTS+=("$obj")
done

clang $SAN \
    -I"$SRC/src" \
    "$HARNESS" "$MAIN_C" "${OBJECTS[@]}" \
    -o "$OUT"
