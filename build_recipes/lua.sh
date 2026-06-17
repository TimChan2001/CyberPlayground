#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/lua: https://www.lua.org/ftp/ @ release_archive lua-5.5.0
#   instances/lua: https://github.com/lua/lua.git @ git_commit 53b41d0cddd80bf33fdc631bdd32e3ba53842b89
# Branch-tip source references are forbidden.
# Build recipe for lua
set -euo pipefail

cd "$SRC"

make clean 2>/dev/null || true
make -j"$(nproc)" \
    CC=clang \
    CFLAGS="$SAN -DLUA_USE_POSIX" \
    MYLIBS="-lm" \
    liblua.a 2>/dev/null

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"

clang $SAN \
    -I"$SRC" \
    "$HARNESS" "$MAIN_C" \
    "$SRC/liblua.a" \
    -lm \
    -o "$OUT"
