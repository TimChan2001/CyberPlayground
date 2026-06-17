#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/zlib: https://github.com/madler/zlib/releases/download/v1.3.2/zlib-1.3.2.tar.xz @ release_tag v1.3.2
# Branch-tip source references are forbidden.
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
OBJ_DIR="$SLOT_DIR/zlib-objects"
mkdir -p "$OBJ_DIR"

SOURCES=(
    adler32.c
    compress.c
    crc32.c
    deflate.c
    gzclose.c
    gzlib.c
    gzread.c
    gzwrite.c
    infback.c
    inffast.c
    inflate.c
    inftrees.c
    trees.c
    uncompr.c
    zutil.c
)

OBJECTS=()
for src in "${SOURCES[@]}"; do
    obj="$OBJ_DIR/${src%.c}.o"
    clang $SAN -DHAVE_UNISTD_H=1 -I"$SRC" -c "$SRC/$src" -o "$obj"
    OBJECTS+=("$obj")
done

clang $SAN \
    -DHAVE_UNISTD_H=1 \
    -I"$SRC" \
    "$HARNESS" "$MAIN_C" "${OBJECTS[@]}" \
    -o "$OUT"
