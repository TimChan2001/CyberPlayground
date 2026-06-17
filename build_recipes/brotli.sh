#!/usr/bin/env bash
# CyberPlayground source revisions:
#   instances/brotli: https://github.com/google/brotli.git @ git_commit af041f55e7bfa3e1bc502f234538e1d6dd6282bd
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
    -DBUILD_SHARED_LIBS=OFF \
    -DBROTLI_BUILD_TESTS=OFF \
    -DBROTLI_DISABLE_TESTS=ON 2>/dev/null
cmake --build "$BUILD_DIR" -j"$JOBS" 2>/dev/null

mapfile -t ARCHIVES < <(find "$BUILD_DIR" -name '*.a' -print)
if [ "${#ARCHIVES[@]}" -eq 0 ]; then
    echo "brotli: no static archives found" >&2
    exit 1
fi

clang $SAN \
    -I"$SRC/c/include" -I"$SRC/c/common" -I"$SRC/c/dec" -I"$SRC/c/enc" \
    "$HARNESS" "$MAIN_C" \
    -Wl,--start-group "${ARCHIVES[@]}" -Wl,--end-group \
    -lm -o "$OUT"
