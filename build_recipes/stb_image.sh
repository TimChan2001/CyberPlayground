#!/usr/bin/env bash
# CyberPlayground source revisions:
#   hard_instances/stb: https://github.com/nothings/stb.git @ git_commit 31c1ad37456438565541f4919958214b6e762fb4
#   instances/stb_image: https://github.com/nothings/stb.git @ git_commit 31c1ad37456438565541f4919958214b6e762fb4
# Branch-tip source references are forbidden.
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
