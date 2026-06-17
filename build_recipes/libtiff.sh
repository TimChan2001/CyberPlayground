#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/libtiff: https://gitlab.com/libtiff/libtiff @ release_tag v4.7.1
#   instances/libtiff: https://github.com/libsdl-org/libtiff.git @ git_commit f43900c82ec8cf7bd02fed22310254972267b3ba
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
    -Dtiff-tools=OFF \
    -Dtiff-tests=OFF \
    -Dtiff-contrib=OFF \
    -Dtiff-docs=OFF \
    -Djpeg=OFF \
    -Dold-jpeg=OFF \
    -Dlzma=OFF \
    -Dlibdeflate=OFF \
    -Dwebp=OFF \
    -Dzstd=OFF \
    -Djbig=OFF \
    -Dzlib=ON 2>/dev/null
cmake --build "$BUILD_DIR" -j"$JOBS" 2>/dev/null

ARCHIVES=()
while IFS= read -r archive; do
    ARCHIVES+=("$archive")
done < <(find "$BUILD_DIR" -name '*.a' -print)
if [ "${#ARCHIVES[@]}" -eq 0 ]; then
    echo "libtiff: no static archives found" >&2
    exit 1
fi

GROUP_START=""
GROUP_END=""
if [ "$(uname -s)" != "Darwin" ]; then
    GROUP_START="-Wl,--start-group"
    GROUP_END="-Wl,--end-group"
fi

clang $SAN \
    -I"$SRC/libtiff" -I"$BUILD_DIR/libtiff" -I"$BUILD_DIR" \
    "$HARNESS" "$MAIN_C" \
    ${GROUP_START:+"$GROUP_START"} "${ARCHIVES[@]}" ${GROUP_END:+"$GROUP_END"} \
    -lz -lm -o "$OUT"
