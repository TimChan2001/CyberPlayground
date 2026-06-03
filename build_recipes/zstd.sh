#!/usr/bin/env bash
set -euo pipefail
cd "$SRC"
make -C lib CC=clang "CFLAGS=$SAN" libzstd.a -j$(nproc) 2>/dev/null
clang -fsanitize=address -g -O1 -I lib -I lib/common "$HARNESS" "$COMMON/main.c" \
  lib/libzstd.a -lm -lpthread -o "$OUT"
