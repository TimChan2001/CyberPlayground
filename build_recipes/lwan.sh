#!/usr/bin/env bash
# CyberPlayground source revisions:
#   instances/lwan: https://github.com/lpereira/lwan.git @ git_commit a32f4885999323b097555e93e6a174fdbb69886e
# Branch-tip source references are forbidden.
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
    -DCMAKE_BUILD_TYPE=Debug \
    -DBUILD_SHARED_LIBS=OFF \
    -DBUILD_TESTING=OFF \
    -DWITH_TESTS=OFF \
    -DWITH_LUA=OFF \
    -DWITH_BROTLI=OFF 2>/dev/null
cmake --build "$BUILD_DIR" -j"$JOBS" 2>/dev/null

mapfile -t ARCHIVES < <(find "$BUILD_DIR" -name '*.a' -print)
if [ "${#ARCHIVES[@]}" -eq 0 ]; then
    echo "lwan: no static archives found" >&2
    exit 1
fi

clang $SAN \
    -I"$SRC/src/lib" -I"$SRC/src/bin" -I"$BUILD_DIR" -I"$BUILD_DIR/src/lib" \
    "$HARNESS" "$MAIN_C" \
    -Wl,--start-group "${ARCHIVES[@]}" -Wl,--end-group \
    -lz -lm -lpthread -ldl -o "$OUT"
