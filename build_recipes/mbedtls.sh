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
    -DENABLE_TESTING=OFF \
    -DENABLE_PROGRAMS=OFF \
    -DMBEDTLS_FATAL_WARNINGS=OFF \
    -DTF_PSA_CRYPTO_FATAL_WARNINGS=OFF \
    -DUSE_SHARED_MBEDTLS_LIBRARY=OFF \
    -DUSE_STATIC_MBEDTLS_LIBRARY=ON 2>/dev/null
cmake --build "$BUILD_DIR" -j"$JOBS" 2>/dev/null

mapfile -t ARCHIVES < <(find "$BUILD_DIR" -name '*.a' -print)
if [ "${#ARCHIVES[@]}" -eq 0 ]; then
    echo "mbedtls: no static archives found" >&2
    exit 1
fi

clang $SAN \
    -I"$SRC/include" -I"$SRC/library" -I"$BUILD_DIR/include" \
    "$HARNESS" "$MAIN_C" \
    -Wl,--start-group "${ARCHIVES[@]}" -Wl,--end-group \
    -lm -o "$OUT"
