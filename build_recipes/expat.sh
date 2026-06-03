#!/usr/bin/env bash
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
SRC_ROOT="$SRC"
if [ -f "$SRC/expat/CMakeLists.txt" ]; then
    SRC_ROOT="$SRC/expat"
fi
BUILD_DIR="$SRC/build-cg"
JOBS="${JOBS:-$(nproc)}"

rm -rf "$BUILD_DIR"
cmake -S "$SRC_ROOT" -B "$BUILD_DIR" \
    -DCMAKE_C_COMPILER=clang \
    -DCMAKE_C_FLAGS="$SAN" \
    -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
    -DBUILD_SHARED_LIBS=OFF \
    -DEXPAT_SHARED_LIBS=OFF \
    -DEXPAT_BUILD_DOCS=OFF \
    -DEXPAT_BUILD_EXAMPLES=OFF \
    -DEXPAT_BUILD_TESTS=OFF \
    -DEXPAT_BUILD_TOOLS=OFF 2>/dev/null
cmake --build "$BUILD_DIR" -j"$JOBS" 2>/dev/null

mapfile -t ARCHIVES < <(find "$BUILD_DIR" -name '*.a' -print)
if [ "${#ARCHIVES[@]}" -eq 0 ]; then
    echo "expat: no static archives found" >&2
    exit 1
fi

clang $SAN \
    -I"$SRC_ROOT/lib" -I"$BUILD_DIR" -I"$BUILD_DIR/lib" \
    "$HARNESS" "$MAIN_C" \
    -Wl,--start-group "${ARCHIVES[@]}" -Wl,--end-group \
    -o "$OUT"
