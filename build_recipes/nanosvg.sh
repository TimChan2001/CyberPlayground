#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/nanosvg: https://github.com/memononen/nanosvg.git @ git_commit 5cefd9847949af6df13f65027fd43af5a7513633
# Branch-tip source references are forbidden.
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
IMPL="$SLOT_DIR/nanosvg_impl.c"

cat > "$IMPL" <<'EOF'
#define NANOSVG_IMPLEMENTATION
#include "nanosvg.h"
#define NANOSVGRAST_IMPLEMENTATION
#include "nanosvgrast.h"
EOF

clang $SAN \
    -I"$SRC/src" \
    "$HARNESS" "$MAIN_C" "$IMPL" \
    -lm -o "$OUT"
