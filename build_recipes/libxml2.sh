#!/usr/bin/env bash
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
BUILD_DIR="$SRC/build-cg"
JOBS="${JOBS:-$(nproc)}"

rm -rf "$BUILD_DIR"
cmake -S "$SRC" -B "$BUILD_DIR" \
    -DCMAKE_C_COMPILER=clang \
    -DCMAKE_C_FLAGS="$SAN" \
    -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
    -DBUILD_SHARED_LIBS=OFF \
    -DLIBXML2_WITH_PYTHON=OFF \
    -DLIBXML2_WITH_TESTS=OFF \
    -DLIBXML2_WITH_PROGRAMS=OFF \
    -DLIBXML2_WITH_LZMA=OFF \
    -DLIBXML2_WITH_ICONV=OFF \
    -DLIBXML2_WITH_ICU=OFF \
    -DLIBXML2_WITH_MODULES=OFF \
    -DLIBXML2_WITH_THREADS=OFF \
    -DLIBXML2_WITH_ZLIB=ON 2>/dev/null
cmake --build "$BUILD_DIR" -j"$JOBS" 2>/dev/null

mapfile -t ARCHIVES < <(find "$BUILD_DIR" -name '*.a' -print)
if [ "${#ARCHIVES[@]}" -eq 0 ]; then
    echo "libxml2: no static archives found" >&2
    exit 1
fi

clang $SAN \
    -I"$SRC/include" -I"$SRC" -I"$BUILD_DIR" -I"$BUILD_DIR/include" \
    "$HARNESS" "$MAIN_C" \
    -Wl,--start-group "${ARCHIVES[@]}" -Wl,--end-group \
    -lz -lm -o "$OUT"
