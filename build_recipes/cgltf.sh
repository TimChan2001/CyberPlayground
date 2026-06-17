#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/cgltf: https://github.com/jkuhlmann/cgltf.git @ git_commit 85cd62382dfea638278962690cf515023f33ed00
# Branch-tip source references are forbidden.
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
IMPL="$SLOT_DIR/cgltf_impl.c"

cat > "$IMPL" <<'EOF'
#define CGLTF_IMPLEMENTATION
#include "cgltf.h"
EOF

clang $SAN \
    -I"$SRC" \
    "$HARNESS" "$MAIN_C" "$IMPL" \
    -lm -o "$OUT"
