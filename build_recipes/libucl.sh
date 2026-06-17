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
    --disable-urls \
    --disable-signatures 2>/dev/null
make -j"$JOBS" 2>/dev/null

ARCHIVES=()
while IFS= read -r archive; do
    ARCHIVES+=("$archive")
done < <(find "$SRC" -name '*.a' -print)
if [ "${#ARCHIVES[@]}" -eq 0 ]; then
    echo "libucl: no static archives found" >&2
    exit 1
fi

GROUP_START=""
GROUP_END=""
if [ "$(uname -s)" != "Darwin" ]; then
    GROUP_START="-Wl,--start-group"
    GROUP_END="-Wl,--end-group"
fi

clang $SAN \
    -I"$SRC/include" -I"$SRC/src" \
    "$HARNESS" "$MAIN_C" \
    ${GROUP_START:+"$GROUP_START"} "${ARCHIVES[@]}" ${GROUP_END:+"$GROUP_END"} \
    -lm -o "$OUT"
