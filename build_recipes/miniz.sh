#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/miniz: https://github.com/richgel999/miniz.git @ git_commit 5cf1e56a9c968c11fdd1a6414f3a95f84314c437
# Branch-tip source references are forbidden.
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
OBJ_DIR="$SLOT_DIR/miniz-objects"
EXPORT_H="$SLOT_DIR/miniz_export.h"
mkdir -p "$OBJ_DIR"

cat > "$EXPORT_H" <<'EOF'
#ifndef MINIZ_EXPORT
#define MINIZ_EXPORT
#endif
EOF

OBJECTS=()
for src in miniz.c miniz_tdef.c miniz_tinfl.c miniz_zip.c; do
    obj="$OBJ_DIR/${src%.c}.o"
    clang $SAN -I"$SLOT_DIR" -I"$SRC" -c "$SRC/$src" -o "$obj"
    OBJECTS+=("$obj")
done

clang $SAN \
    -I"$SLOT_DIR" \
    -I"$SRC" \
    "$HARNESS" "$MAIN_C" "${OBJECTS[@]}" \
    -lm -o "$OUT"
