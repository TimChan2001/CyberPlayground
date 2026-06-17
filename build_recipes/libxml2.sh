#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/libxml2: https://gitlab.gnome.org/GNOME/libxml2 @ release_tag v2.15.3
#   instances/libxml2: https://gitlab.gnome.org/GNOME/libxml2.git @ git_commit b15a388a6148e1a61c52f2c057b4554db08ce808
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
    -DLIBXML2_WITH_PYTHON=OFF \
    -DLIBXML2_WITH_TESTS=OFF \
    -DLIBXML2_WITH_PROGRAMS=OFF \
    -DLIBXML2_WITH_LZMA=OFF \
    -DLIBXML2_WITH_ICONV=OFF \
    -DLIBXML2_WITH_ICU=OFF \
    -DLIBXML2_WITH_MODULES=OFF \
    -DLIBXML2_WITH_THREADS=OFF \
    -DLIBXML2_WITH_ZLIB=ON 2>/dev/null
cmake --build "$BUILD_DIR" -j"$JOBS" 2>/dev/null

ARCHIVES=()
while IFS= read -r archive; do
    ARCHIVES+=("$archive")
done < <(find "$BUILD_DIR" -name '*.a' -print)
if [ "${#ARCHIVES[@]}" -eq 0 ]; then
    echo "libxml2: no static archives found" >&2
    exit 1
fi

GROUP_START=""
GROUP_END=""
if [ "$(uname -s)" != "Darwin" ]; then
    GROUP_START="-Wl,--start-group"
    GROUP_END="-Wl,--end-group"
fi

clang $SAN \
    -I"$SRC/include" -I"$SRC" -I"$BUILD_DIR" -I"$BUILD_DIR/include" \
    "$HARNESS" "$MAIN_C" \
    ${GROUP_START:+"$GROUP_START"} "${ARCHIVES[@]}" ${GROUP_END:+"$GROUP_END"} \
    -lz -lm -o "$OUT"
