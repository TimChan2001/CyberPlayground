#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/expat: https://github.com/libexpat/libexpat @ release_tag R_2_8_1
#   instances/expat: https://github.com/libexpat/libexpat.git @ git_commit c7ffbf3879f6aef7a7b020ef84ddb4ee00222b19
# Branch-tip source references are forbidden.
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

ARCHIVES=()
while IFS= read -r archive; do
    ARCHIVES+=("$archive")
done < <(find "$BUILD_DIR" -name '*.a' -print)
if [ "${#ARCHIVES[@]}" -eq 0 ]; then
    echo "expat: no static archives found" >&2
    exit 1
fi

GROUP_START=""
GROUP_END=""
if [ "$(uname -s)" != "Darwin" ]; then
    GROUP_START="-Wl,--start-group"
    GROUP_END="-Wl,--end-group"
fi

clang $SAN \
    -I"$SRC_ROOT/lib" -I"$BUILD_DIR" -I"$BUILD_DIR/lib" \
    "$HARNESS" "$MAIN_C" \
    ${GROUP_START:+"$GROUP_START"} "${ARCHIVES[@]}" ${GROUP_END:+"$GROUP_END"} \
    -o "$OUT"
