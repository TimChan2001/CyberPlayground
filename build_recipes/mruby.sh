#!/usr/bin/env bash
# CyberPlayground source revisions:
#   instances/mruby: https://github.com/mruby/mruby.git @ git_commit 16151a0daad0c74bcc502a790c83192d396717ab
# Branch-tip source references are forbidden.
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
JOBS="${JOBS:-$(nproc)}"

if ! command -v ruby >/dev/null 2>&1; then
    echo "mruby: ruby is required to run minirake" >&2
    exit 1
fi

./minirake clean 2>/dev/null || true
CC=clang CFLAGS="$SAN -fPIC" LDFLAGS="$SAN" ./minirake -j"$JOBS" 2>/dev/null

LIB="$SRC/build/host/lib/libmruby.a"
if [ ! -f "$LIB" ]; then
    echo "mruby: build/host/lib/libmruby.a was not produced" >&2
    exit 1
fi

clang $SAN \
    -I"$SRC/include" -I"$SRC/build/host/include" \
    "$HARNESS" "$MAIN_C" "$LIB" \
    -lm -ldl -o "$OUT"
