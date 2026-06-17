#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/dr_mp3: https://github.com/mackron/dr_libs.git @ git_commit 243e26ffa08a24dc8ae2e7a8c57123d9e504690c
# Branch-tip source references are forbidden.
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
IMPL="$SLOT_DIR/dr_mp3_impl.c"

cat > "$IMPL" <<'EOF'
#define DR_MP3_IMPLEMENTATION
#include "dr_mp3.h"
EOF

clang $SAN \
    -I"$SRC" \
    "$HARNESS" "$MAIN_C" "$IMPL" \
    -lm -o "$OUT"
