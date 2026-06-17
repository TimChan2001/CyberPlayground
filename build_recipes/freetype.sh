#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/freetype: https://gitlab.freedesktop.org/freetype/freetype @ release_tag VER-2-14-3
#   instances/freetype: https://github.com/freetype/freetype.git @ git_commit fae1e3160e727ae1fc19c54e54d71e9bd1d0c917
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
    -DFT_DISABLE_ZLIB=TRUE \
    -DFT_DISABLE_BZIP2=TRUE \
    -DFT_DISABLE_PNG=TRUE \
    -DFT_DISABLE_HARFBUZZ=TRUE \
    -DFT_DISABLE_BROTLI=TRUE 2>/dev/null
cmake --build "$BUILD_DIR" -j"$JOBS" 2>/dev/null

ARCHIVES=()
while IFS= read -r archive; do
    ARCHIVES+=("$archive")
done < <(find "$BUILD_DIR" -name '*.a' -print)
if [ "${#ARCHIVES[@]}" -eq 0 ]; then
    echo "freetype: no static archives found" >&2
    exit 1
fi

GROUP_START=""
GROUP_END=""
if [ "$(uname -s)" != "Darwin" ]; then
    GROUP_START="-Wl,--start-group"
    GROUP_END="-Wl,--end-group"
fi

clang $SAN \
    -I"$SRC/include" -I"$BUILD_DIR/include" \
    "$HARNESS" "$MAIN_C" \
    ${GROUP_START:+"$GROUP_START"} "${ARCHIVES[@]}" ${GROUP_END:+"$GROUP_END"} \
    -lm -o "$OUT"
