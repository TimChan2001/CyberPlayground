#!/usr/bin/env bash
set -euo pipefail

cd "$SRC"

SLOT_DIR="$(dirname "$OUT")"
HARNESS="${HARNESS:-$SLOT_DIR/harness.c}"
MAIN_C="${COMMON:-}/main.c"
IMPL="$SLOT_DIR/stb_image_impl.c"

cat > "$IMPL" <<'EOF'
#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"
EOF

clang $SAN \
    -I"$SRC" \
    "$HARNESS" "$MAIN_C" "$IMPL" \
    -lm -o "$OUT"
