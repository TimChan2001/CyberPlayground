#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/libucl: https://github.com/vstakhov/libucl @ release_tag 0.9.4
#   instances/libucl: https://github.com/vstakhov/libucl.git @ git_commit e4b95c6c60e2a4aa79def894b59fdcecf9928e1a
# Branch-tip source references are forbidden.
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"

BUILD_DIR="$SLOT_DIR/libucl-build"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

COMMON_CFLAGS=(
    $SAN
    -fPIC
    -O1
    -g
    -I"$SRC/include"
    -I"$SRC/src"
    -I"$SRC/uthash"
    -I"$SRC/klib"
    -Wno-unused-parameter
    -Wno-pointer-sign
    -DHAVE_ATOMIC_BUILTINS=1
)

SOURCES=(
    src/ucl_util.c
    src/ucl_parser.c
    src/ucl_emitter.c
    src/ucl_emitter_streamline.c
    src/ucl_emitter_utils.c
    src/ucl_hash.c
    src/ucl_schema.c
    src/ucl_msgpack.c
    src/ucl_sexp.c
)

OBJECTS=()
for src_file in "${SOURCES[@]}"; do
    obj="$BUILD_DIR/$(basename "$src_file" .c).o"
    clang "${COMMON_CFLAGS[@]}" -c "$SRC/$src_file" -o "$obj"
    OBJECTS+=("$obj")
done

clang $SAN \
    -I"$SRC/include" -I"$SRC/src" \
    "$HARNESS" "$MAIN_C" \
    "${OBJECTS[@]}" \
    -lm -o "$OUT"
