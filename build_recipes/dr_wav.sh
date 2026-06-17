#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/dr_wav: https://github.com/mackron/dr_libs.git @ git_commit 243e26ffa08a24dc8ae2e7a8c57123d9e504690c
# Branch-tip source references are forbidden.
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
IMPL="$SLOT_DIR/dr_wav_impl.c"

cat > "$IMPL" <<'EOF'
#define DR_WAV_IMPLEMENTATION
#include "dr_wav.h"
EOF

clang $SAN \
    -I"$SRC" \
    "$HARNESS" "$MAIN_C" "$IMPL" \
    -lm -o "$OUT"
