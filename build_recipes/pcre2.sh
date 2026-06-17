#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/pcre2: https://github.com/PCRE2Project/pcre2 @ release_tag pcre2-10.47
#   instances/pcre2: https://github.com/PCRE2Project/pcre2.git @ git_commit 4f460e5edaa698bda57a93e044ca811fe64e93f8
# Branch-tip source references are forbidden.
# Build recipe for pcre2 (Tier 1 CyberGym project)
#
# Env vars (set by caller):
#   SRC     - path to pcre2 source tree
#   OUT     - output binary path (e.g. slot/harness.vul)
#   SAN     - sanitizer flags
#   HARNESS - path to harness.c (optional)
#   COMMON  - path to _common/ dir (for main.c)
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"

# Try cmake first (faster, simpler), fall back to autotools
if command -v cmake &>/dev/null; then
    cmake -DCMAKE_C_COMPILER=clang \
          -DCMAKE_C_FLAGS="$SAN" \
          -DPCRE2_SUPPORT_UNICODE=ON \
          -DPCRE2_SUPPORT_JIT=OFF \
          -DPCRE2_BUILD_TESTS=OFF \
          -DPCRE2_BUILD_PCRE2GREP=OFF \
          -DBUILD_SHARED_LIBS=OFF \
          -B build -S . 2>/dev/null

    cmake --build build -j"$(nproc)" --target pcre2-8-static 2>/dev/null

    clang $SAN \
        -I"$SRC/src" -I"$SRC/build/interface" \
        "$HARNESS" "$MAIN_C" \
        -L"$SRC/build" -lpcre2-8 \
        -o "$OUT"
else
    # Autotools (matches OSS-Fuzz build)
    ./autogen.sh 2>/dev/null || true
    CC=clang CFLAGS="$SAN" ./configure \
        --enable-unicode --disable-jit --disable-shared --enable-static \
        --disable-pcre2grep 2>/dev/null
    make -j"$(nproc)" clean 2>/dev/null || true
    make -j"$(nproc)" 2>/dev/null

    clang $SAN \
        -I"$SRC/src" \
        "$HARNESS" "$MAIN_C" \
        .libs/libpcre2-8.a \
        -o "$OUT"
fi
