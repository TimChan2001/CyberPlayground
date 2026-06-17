#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/giflib: https://sourceforge.net/projects/giflib/files/giflib-5.2.2.tar.gz/download @ release_archive giflib-5.2.2
#   instances/giflib: https://git.code.sf.net/p/giflib/code @ git_commit edff4aed17f857442ab0cac31566572ba08f93d3
# Branch-tip source references are forbidden.
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
JOBS="${JOBS:-$(nproc)}"

make clean 2>/dev/null || true
make -j"$JOBS" CC=clang CFLAGS="$SAN -fPIC" libgif.a 2>/dev/null

if [ ! -f "$SRC/libgif.a" ]; then
    echo "giflib: libgif.a was not produced" >&2
    exit 1
fi

clang $SAN \
    -I"$SRC" \
    "$HARNESS" "$MAIN_C" "$SRC/libgif.a" \
    -lm -o "$OUT"
