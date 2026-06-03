#!/usr/bin/env bash
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
BUILD_DIR="$SRC/build-cg"
JOBS="${JOBS:-$(nproc)}"
XML_CFLAGS="$(pkg-config --cflags libxml-2.0 2>/dev/null || true)"
XML_LIBS="$(pkg-config --libs libxml-2.0 2>/dev/null || echo -lxml2)"

rm -rf "$BUILD_DIR"
if [ -f "$SRC/CMakeLists.txt" ]; then
    cmake -S "$SRC" -B "$BUILD_DIR" \
        -DCMAKE_C_COMPILER=clang \
        -DCMAKE_C_FLAGS="$SAN" \
        -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
        -DBUILD_SHARED_LIBS=OFF \
        -DLIBXSLT_WITH_CRYPTO=OFF \
        -DLIBXSLT_WITH_DEBUGGER=OFF \
        -DLIBXSLT_WITH_MODULES=OFF \
        -DLIBXSLT_WITH_PYTHON=OFF \
        -DLIBXSLT_WITH_TESTS=OFF \
        -DLIBXSLT_WITH_PROFILER=OFF 2>/dev/null
    cmake --build "$BUILD_DIR" -j"$JOBS" 2>/dev/null
else
    if [ -x ./autogen.sh ]; then
        ./autogen.sh 2>/dev/null || true
    else
        autoreconf -fi 2>/dev/null || true
    fi
    make clean 2>/dev/null || true
    ASAN_OPTIONS=detect_leaks=0 CC=clang CFLAGS="$SAN -fPIC $XML_CFLAGS" ./configure \
        --disable-shared \
        --enable-static \
        --without-python \
        --without-crypto \
        --without-debugger \
        --without-plugins 2>/dev/null
    make -j"$JOBS" 2>/dev/null
fi

mapfile -t ARCHIVES < <(find "$SRC" "$BUILD_DIR" -name '*.a' -print 2>/dev/null)
if [ "${#ARCHIVES[@]}" -eq 0 ]; then
    echo "libxslt: no static archives found" >&2
    exit 1
fi

clang $SAN \
    -I"$SRC" -I"$SRC/libxslt" -I"$BUILD_DIR" $XML_CFLAGS \
    "$HARNESS" "$MAIN_C" \
    -Wl,--start-group "${ARCHIVES[@]}" -Wl,--end-group \
    $XML_LIBS -lz -lm -o "$OUT"
