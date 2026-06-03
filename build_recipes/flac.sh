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
    -DBUILD_PROGRAMS=OFF \
    -DBUILD_EXAMPLES=OFF \
    -DBUILD_TESTING=OFF \
    -DBUILD_DOCS=OFF \
    -DINSTALL_MANPAGES=OFF \
    -DWITH_OGG=OFF \
    -DWITH_STACK_PROTECTOR=OFF 2>/dev/null
cmake --build "$BUILD_DIR" -j"$JOBS" 2>/dev/null

mapfile -t ARCHIVES < <(find "$BUILD_DIR" -name '*.a' -print)
if [ "${#ARCHIVES[@]}" -eq 0 ]; then
    echo "flac: no static archives found" >&2
    exit 1
fi

clang $SAN \
    -I"$SRC/include" -I"$SRC/src/libFLAC/include" -I"$BUILD_DIR/include" \
    "$HARNESS" "$MAIN_C" \
    -Wl,--start-group "${ARCHIVES[@]}" -Wl,--end-group \
    -lm -o "$OUT"
