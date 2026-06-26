#!/usr/bin/env bash
# Operator wrapper for running CLI agents against CyberPlayground evals.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

API="${PLAYGROUND_API:-http://127.0.0.1:10382}"
LOG_BASE="${CYBERPLAYGROUND_LOG_BASE:-/tmp/cyberplayground-logs}"
DEFAULT_TIMEOUT="${TASK_TIMEOUT:-1800}"
DEFAULT_RESULT_WAIT="${RESULT_WAIT:-180}"
DEFAULT_SANDBOX="${CODEX_SANDBOX:-danger-full-access}"

usage() {
    cat <<'EOF'
Usage:
  scripts/codex_eval.sh doctor
  scripts/codex_eval.sh sample [sample_instances.py options]
  scripts/codex_eval.sh queue <agent_id> [--tier T0|T1|T2] [--project NAME] [--ids-file FILE]
  scripts/codex_eval.sh start <agent_id> [--timeout SEC] [--result-wait SEC] [--sandbox NAME]
  scripts/codex_eval.sh status <agent_id>
  scripts/codex_eval.sh report <agent_id>
  scripts/codex_eval.sh logs <agent_id> [-n LINES]
  scripts/codex_eval.sh pretty <agent_id> [ccr_watch_pretty.sh options]
  scripts/codex_eval.sh pid <agent_id>
  scripts/codex_eval.sh stop <agent_id>

Environment:
  PLAYGROUND_API              API base URL, default http://127.0.0.1:10382
  CYBERPLAYGROUND_LOG_BASE    Log root, default /tmp/cyberplayground-logs
  TASK_TIMEOUT                Per-task timeout for start, default 1800
  RESULT_WAIT                 Post-agent status wait, default 180
  CODEX_SANDBOX               Codex sandbox for start, default danger-full-access

Recommended Codex command launched by start:
  codex -a never exec --sandbox danger-full-access --json -

Recommended CCR Code command for manual run_agent.sh:
  ccr code -p --permission-mode auto --output-format stream-json --include-partial-messages --verbose
EOF
}

die() {
    echo "error: $*" >&2
    exit 1
}

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "$1 is required"
}

log_dir_for() {
    printf '%s/%s\n' "$LOG_BASE" "$1"
}

pid_file_for() {
    printf '%s/runner.pid\n' "$(log_dir_for "$1")"
}

runner_alive() {
    local pid="$1"
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

read_pid() {
    local pid_file="$1"
    if [ -f "$pid_file" ]; then
        tr -d '[:space:]' < "$pid_file"
    fi
    return 0
}

cmd_doctor() {
    require_cmd curl
    require_cmd python3

    echo "repo: $REPO_ROOT"
    echo "api:  $API"
    echo

    if command -v codex >/dev/null 2>&1; then
        codex --version || true
    else
        echo "codex: not found"
    fi

    echo
    curl -sS "$API/health" | python3 -m json.tool
}

cmd_sample() {
    exec python3 "$REPO_ROOT/scripts/sample_instances.py" "$@"
}

cmd_queue() {
    require_cmd python3
    require_cmd curl

    local agent_id="${1:-}"
    [ -n "$agent_id" ] || die "queue requires <agent_id>"
    shift || true

    local tier="T0"
    local project=""
    local ids_file=""

    while [ "$#" -gt 0 ]; do
        case "$1" in
            --tier)
                tier="${2:-}"
                [ -n "$tier" ] || die "--tier requires a value"
                shift 2
                ;;
            --project)
                project="${2:-}"
                [ -n "$project" ] || die "--project requires a value"
                shift 2
                ;;
            --ids-file)
                ids_file="${2:-}"
                [ -n "$ids_file" ] || die "--ids-file requires a value"
                shift 2
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                die "unknown queue option: $1"
                ;;
        esac
    done

    local cmd=(python3 "$REPO_ROOT/scripts/run_eval.py"
        --agent-id "$agent_id"
        --tier "$tier"
        --no-launch)

    if [ -n "$project" ]; then
        cmd+=(--project "$project")
    fi

    if [ -n "$ids_file" ]; then
        [ -f "$ids_file" ] || die "ids file not found: $ids_file"
        mapfile -t ids < <(sed '/^[[:space:]]*$/d' "$ids_file")
        [ "${#ids[@]}" -gt 0 ] || die "ids file is empty: $ids_file"
        cmd+=(--instance-ids "${ids[@]}")
    fi

    cd "$REPO_ROOT"
    PLAYGROUND_API="$API" "${cmd[@]}"
}

cmd_start() {
    require_cmd codex
    require_cmd setsid

    local agent_id="${1:-}"
    [ -n "$agent_id" ] || die "start requires <agent_id>"
    shift || true

    local timeout="$DEFAULT_TIMEOUT"
    local result_wait="$DEFAULT_RESULT_WAIT"
    local sandbox="$DEFAULT_SANDBOX"

    while [ "$#" -gt 0 ]; do
        case "$1" in
            --timeout)
                timeout="${2:-}"
                [ -n "$timeout" ] || die "--timeout requires seconds"
                shift 2
                ;;
            --result-wait)
                result_wait="${2:-}"
                [ -n "$result_wait" ] || die "--result-wait requires seconds"
                shift 2
                ;;
            --sandbox)
                sandbox="${2:-}"
                [ -n "$sandbox" ] || die "--sandbox requires a value"
                shift 2
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                die "unknown start option: $1"
                ;;
        esac
    done

    local log_dir
    log_dir="$(log_dir_for "$agent_id")"
    local pid_file="$log_dir/runner.pid"
    local out_file="$log_dir/runner.out"
    local run_file="$log_dir/run.sh"

    mkdir -p "$log_dir"

    local existing_pid
    existing_pid="$(read_pid "$pid_file")"
    if runner_alive "$existing_pid"; then
        die "runner already active for $agent_id (pid $existing_pid)"
    fi

    {
        printf '#!/usr/bin/env bash\n'
        printf 'set -euo pipefail\n'
        printf 'cd %q\n' "$REPO_ROOT"
        printf 'export PLAYGROUND_API=%q\n' "$API"
        printf 'export TASK_TIMEOUT=%q\n' "$timeout"
        printf 'export RESULT_WAIT=%q\n' "$result_wait"
        printf 'exec ./scripts/run_agent.sh %q codex -a never exec --sandbox %q --json -\n' \
            "$agent_id" "$sandbox"
    } > "$run_file"
    chmod +x "$run_file"

    setsid "$run_file" > "$out_file" 2>&1 < /dev/null &
    local pid="$!"
    printf '%s\n' "$pid" > "$pid_file"

    echo "started: $agent_id"
    echo "pid:     $pid"
    echo "log:     $out_file"
    echo "command: codex -a never exec --sandbox $sandbox --json -"
}

cmd_status() {
    require_cmd curl
    require_cmd python3

    local agent_id="${1:-}"
    [ -n "$agent_id" ] || die "status requires <agent_id>"

    curl -sS "$API/eval/$agent_id/pending" | python3 -m json.tool
}

cmd_report() {
    require_cmd curl
    require_cmd python3

    local agent_id="${1:-}"
    [ -n "$agent_id" ] || die "report requires <agent_id>"

    curl -sS "$API/eval/$agent_id/report" | python3 -m json.tool
}

cmd_logs() {
    local agent_id="${1:-}"
    [ -n "$agent_id" ] || die "logs requires <agent_id>"
    shift || true

    local lines="120"
    while [ "$#" -gt 0 ]; do
        case "$1" in
            -n)
                lines="${2:-}"
                [ -n "$lines" ] || die "-n requires a value"
                shift 2
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                die "unknown logs option: $1"
                ;;
        esac
    done

    local out_file
    out_file="$(log_dir_for "$agent_id")/runner.out"
    [ -f "$out_file" ] || die "runner log not found: $out_file"
    tail -n "$lines" -f "$out_file"
}

cmd_pretty() {
    local agent_id="${1:-}"
    [ -n "$agent_id" ] || die "pretty requires <agent_id>"

    exec "$REPO_ROOT/scripts/ccr_watch_pretty.sh" "$@"
}

cmd_pid() {
    local agent_id="${1:-}"
    [ -n "$agent_id" ] || die "pid requires <agent_id>"

    local pid
    pid="$(read_pid "$(pid_file_for "$agent_id")")"
    if runner_alive "$pid"; then
        echo "$pid running"
    elif [ -n "$pid" ]; then
        echo "$pid not-running"
    else
        echo "no pid file"
    fi
}

cmd_stop() {
    local agent_id="${1:-}"
    [ -n "$agent_id" ] || die "stop requires <agent_id>"

    local pid_file
    pid_file="$(pid_file_for "$agent_id")"
    local pid
    pid="$(read_pid "$pid_file")"

    if ! runner_alive "$pid"; then
        echo "no active runner for $agent_id"
        return 0
    fi

    kill "$pid"
    echo "stopped $agent_id (pid $pid)"
}

main() {
    local command="${1:-help}"
    if [ "$#" -gt 0 ]; then
        shift
    fi

    case "$command" in
        doctor) cmd_doctor "$@" ;;
        sample) cmd_sample "$@" ;;
        queue) cmd_queue "$@" ;;
        start) cmd_start "$@" ;;
        status) cmd_status "$@" ;;
        report) cmd_report "$@" ;;
        logs) cmd_logs "$@" ;;
        pretty) cmd_pretty "$@" ;;
        pid) cmd_pid "$@" ;;
        stop) cmd_stop "$@" ;;
        -h|--help|help) usage ;;
        *) die "unknown command: $command" ;;
    esac
}

main "$@"
