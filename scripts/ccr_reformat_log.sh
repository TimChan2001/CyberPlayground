#!/usr/bin/env bash
# Deterministically reformat a saved raw CCR stream-json task log.
#
# This wraps ../reformat_ccr_log.py. It does not call ccr code and does not
# modify raw logs.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FORMATTER="$REPO_ROOT/reformat_ccr_log.py"

usage() {
    cat <<'EOF'
Usage:
  scripts/ccr_reformat_log.sh <task-log>
  cat <task-log> | scripts/ccr_reformat_log.sh -

Environment:
  CCR_REFORMAT_BYTES    Bytes from the end of the log to parse.
                        Default 0 means parse the full log.
  CCR_REFORMAT_STYLE    compact or markdown, default compact
  CCR_REFORMAT_COLOR    auto, always, or never; default always for compact

Example:
  scripts/ccr_reformat_log.sh \
    /tmp/cyberplayground-logs/ccr-t0-100-20260601-115309/T1_giflib_0013_task_89508d98e559.log
EOF
}

die() {
    echo "error: $*" >&2
    exit 1
}

is_uint() {
    case "$1" in
        ''|*[!0-9]*) return 1 ;;
        *) return 0 ;;
    esac
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    usage
    exit 0
fi

LOG="${1:-}"
[ -n "$LOG" ] || die "missing task log path"
[ -f "$FORMATTER" ] || die "formatter not found: $FORMATTER"

BYTES="${CCR_REFORMAT_BYTES:-0}"
STYLE="${CCR_REFORMAT_STYLE:-compact}"
COLOR="${CCR_REFORMAT_COLOR:-always}"
is_uint "$BYTES" || die "CCR_REFORMAT_BYTES must be a non-negative integer"
case "$STYLE" in
    compact|markdown) ;;
    *) die "CCR_REFORMAT_STYLE must be compact or markdown" ;;
esac
case "$COLOR" in
    auto|always|never) ;;
    *) die "CCR_REFORMAT_COLOR must be auto, always, or never" ;;
esac

SNIPPET="$(mktemp)"
OUTPUT="$(mktemp)"
cleanup() {
    rm -f "$SNIPPET" "$OUTPUT"
}
trap cleanup EXIT

if [ "$LOG" = "-" ]; then
    cat > "$SNIPPET"
elif [ -f "$LOG" ]; then
    if [ "$BYTES" = "0" ]; then
        cat "$LOG" > "$SNIPPET"
    else
        tail -c "$BYTES" "$LOG" > "$SNIPPET"
    fi
else
    die "log not found: $LOG"
fi

python3 "$FORMATTER" --style "$STYLE" --color "$COLOR" "$SNIPPET" "$OUTPUT" >/dev/null
cat "$OUTPUT"
