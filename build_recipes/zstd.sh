#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/zstd: https://github.com/facebook/zstd @ release_tag v1.5.7
#   instances/zstd: https://github.com/facebook/zstd.git @ git_commit 885c79ba4ae8345e006f61bc97b270d4cf7ff076
# Branch-tip source references are forbidden.
set -euo pipefail
cd "$SRC"
make -C lib CC=clang "CFLAGS=$SAN" libzstd.a -j$(nproc) 2>/dev/null
clang -fsanitize=address -g -O1 -I lib -I lib/common "$HARNESS" "$COMMON/main.c" \
  lib/libzstd.a -lm -lpthread -o "$OUT"
