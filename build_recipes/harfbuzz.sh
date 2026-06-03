#!/usr/bin/env bash
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
BUILD_DIR="$SRC/build-cg"
JOBS="${JOBS:-$(nproc)}"

rm -rf "$BUILD_DIR"
if [ -f "$SRC/CMakeLists.txt" ]; then
    cmake -S "$SRC" -B "$BUILD_DIR" \
        -DCMAKE_C_COMPILER=clang \
        -DCMAKE_CXX_COMPILER=clang++ \
        -DCMAKE_C_FLAGS="$SAN" \
        -DCMAKE_CXX_FLAGS="$SAN" \
        -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
        -DBUILD_SHARED_LIBS=OFF \
        -DHB_BUILD_UTILS=OFF \
        -DHB_BUILD_TESTS=OFF \
        -DHB_BUILD_SUBSET=ON \
        -DHB_HAVE_FREETYPE=OFF \
        -DHB_HAVE_GLIB=OFF \
        -DHB_HAVE_GOBJECT=OFF \
        -DHB_HAVE_CAIRO=OFF \
        -DHB_HAVE_ICU=OFF 2>/dev/null
    cmake --build "$BUILD_DIR" -j"$JOBS" 2>/dev/null
elif command -v meson >/dev/null 2>&1; then
    meson setup "$BUILD_DIR" "$SRC" \
        --default-library=static \
        -Dtests=disabled -Dutilities=disabled -Ddocs=disabled \
        -Dfreetype=disabled -Dglib=disabled -Dgobject=disabled \
        -Dcairo=disabled -Dicu=disabled \
        --native-file <(printf '[binaries]\nc = "clang"\ncpp = "clang++"\n\n[built-in options]\nc_args = [%s]\ncpp_args = [%s]\n' "\"${SAN// /\", \"}\"" "\"${SAN// /\", \"}\"") 2>/dev/null
    meson compile -C "$BUILD_DIR" -j"$JOBS" 2>/dev/null
else
    echo "harfbuzz: CMakeLists.txt not found and meson is unavailable" >&2
    exit 1
fi

mapfile -t ARCHIVES < <(find "$BUILD_DIR" -name '*.a' -print)
if [ "${#ARCHIVES[@]}" -eq 0 ]; then
    echo "harfbuzz: no static archives found" >&2
    exit 1
fi

clang++ $SAN \
    -I"$SRC/src" -I"$BUILD_DIR/src" -I"$BUILD_DIR" \
    "$HARNESS" "$MAIN_C" \
    -Wl,--start-group "${ARCHIVES[@]}" -Wl,--end-group \
    -lm -lpthread -o "$OUT"
