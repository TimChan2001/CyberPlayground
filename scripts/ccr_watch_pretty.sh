#!/usr/bin/env bash
# Periodically reformat the newest raw CCR task log for an active eval run.
#
# This is a sidecar viewer. It does not modify the runner, tasks, raw logs, or
# agent output stream.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_BASE="${CYBERPLAYGROUND_LOG_BASE:-/tmp/cyberplayground-logs}"

usage() {
    cat <<'EOF'
Usage:
  scripts/ccr_watch_pretty.sh <agent_id> [options]

Options:
  --interval SEC       Seconds between checks, default 15
  --bytes N            Bytes from the end of the task log to reformat,
                       default 0 for the full log
  --timeout SEC        Seconds before killing each reformat call, default 30
  --output FILE        Output file, default /tmp/cyberplayground-logs/<agent>/runner.pretty.out
  --tail-lines N       Lines to print after each refresh, default 80;
                       use 0 to print the full formatted output
  --once               Reformat once and exit

Environment:
  CYBERPLAYGROUND_LOG_BASE    Log root, default /tmp/cyberplayground-logs
  CCR_REFORMAT_BYTES          Bytes from end of log to parse, default 0
  CCR_REFORMAT_TIMEOUT        Seconds before killing each reformat call, default 30

Example:
  scripts/ccr_watch_pretty.sh ccr-t0-100-20260601-115309 --interval 15
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

latest_task_log() {
    local log_dir="$1"
    find "$log_dir" -maxdepth 1 -type f -name '*.log' -printf '%T@ %p\n' 2>/dev/null \
        | sort -nr \
        | awk 'NR == 1 { sub(/^[^ ]+ /, ""); print; exit }'
}

agent_id="${1:-}"
if [ "$agent_id" = "-h" ] || [ "$agent_id" = "--help" ]; then
    usage
    exit 0
fi
[ -n "$agent_id" ] || die "missing <agent_id>"
shift || true

interval=15
bytes="${CCR_REFORMAT_BYTES:-0}"
timeout_s="${CCR_REFORMAT_TIMEOUT:-30}"
once=0
tail_lines="${CCR_PRETTY_TAIL_LINES:-80}"

log_dir="$LOG_BASE/$agent_id"
output="$log_dir/runner.pretty.out"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --interval)
            interval="${2:-}"
            [ -n "$interval" ] || die "--interval requires seconds"
            shift 2
            ;;
        --bytes)
            bytes="${2:-}"
            [ -n "$bytes" ] || die "--bytes requires a value"
            shift 2
            ;;
        --timeout)
            timeout_s="${2:-}"
            [ -n "$timeout_s" ] || die "--timeout requires seconds"
            shift 2
            ;;
        --output)
            output="${2:-}"
            [ -n "$output" ] || die "--output requires a file"
            shift 2
            ;;
        --tail-lines)
            tail_lines="${2:-}"
            [ -n "$tail_lines" ] || die "--tail-lines requires a value"
            shift 2
            ;;
        --once)
            once=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "unknown option: $1"
            ;;
    esac
done

is_uint "$interval" || die "--interval must be a non-negative integer"
is_uint "$bytes" || die "--bytes must be a non-negative integer"
is_uint "$timeout_s" || die "--timeout must be a non-negative integer"
is_uint "$tail_lines" || die "--tail-lines must be a non-negative integer"
[ "$once" -eq 1 ] || [ "$interval" -gt 0 ] || die "--interval must be greater than 0 unless --once is used"
[ -d "$log_dir" ] || die "log directory not found: $log_dir"

mkdir -p "$(dirname "$output")"

last_key=""

echo "watching: $log_dir"
echo "output:   $output"
echo "interval: ${interval}s"
echo "bytes:    $bytes"
echo "tail:     ${tail_lines} lines"
echo "stop:     Ctrl-C"
echo

while true; do
    log_file="$(latest_task_log "$log_dir")"

    if [ -z "$log_file" ]; then
        echo "[$(date -u +%H:%M:%S)] no task logs yet"
    else
        key="$(stat -c '%n:%s:%Y' "$log_file")"
        if [ "$key" != "$last_key" ]; then
            tmp="$(mktemp)"
            err="$(mktemp)"
            header="== CCR formatted view: $(basename "$log_file") @ $(date -u +%Y-%m-%dT%H:%M:%SZ) =="
            echo "[$(date -u +%H:%M:%S)] refreshing $(basename "$log_file")"

            if CCR_REFORMAT_BYTES="$bytes" \
                timeout "$timeout_s" "$SCRIPT_DIR/ccr_reformat_log.sh" "$log_file" > "$tmp" 2>"$err"; then
                {
                    echo "$header"
                    echo
                    cat "$tmp"
                } > "$output"
                if [ "$tail_lines" = "0" ]; then
                    cat "$output"
                else
                    tail -n "$tail_lines" "$output"
                fi
                echo
                last_key="$key"
            else
                {
                    echo "$header"
                    echo
                    echo "CCR reformat failed."
                    if [ -s "$err" ]; then
                        echo
                        cat "$err"
                    fi
                } > "$output"
                cat "$output"
                echo
            fi
            rm -f "$tmp" "$err"
        fi
    fi

    if [ "$once" -eq 1 ]; then
        break
    fi
    sleep "$interval"
done
