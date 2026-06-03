#!/usr/bin/env bash
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
JOBS="${JOBS:-$(nproc)}"

if [ -x ./autogen.sh ]; then
    ./autogen.sh 2>/dev/null || true
else
    autoreconf -fi 2>/dev/null || true
fi

make clean 2>/dev/null || true
ASAN_OPTIONS=detect_leaks=0 CC=clang CFLAGS="$SAN -fPIC" ./configure \
    --disable-shared \
    --enable-static \
    --with-only-libndpi 2>/dev/null
make -j"$JOBS" 2>/dev/null

mapfile -t ARCHIVES < <(find "$SRC" -name '*.a' -print)
if [ "${#ARCHIVES[@]}" -eq 0 ]; then
    echo "ndpi: no static archives found" >&2
    exit 1
fi

clang $SAN \
    -I"$SRC/src/include" -I"$SRC/src/lib" -I"$SRC" \
    "$HARNESS" "$MAIN_C" \
    -Wl,--start-group "${ARCHIVES[@]}" -Wl,--end-group \
    -lm -lpthread -ldl -o "$OUT"
