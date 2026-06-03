# CyberPlayground Agent Testing Runbook

This runbook covers running CLI agents against queued CyberPlayground tasks.
The benchmark model is one fresh agent process per task, with no context shared
between tasks.

Supported local workflows:

- Codex CLI through `scripts/codex_eval.sh start`.
- Claude Code through CCR Code Router, using `ccr code` directly. Do not call a
  `claude` command for this workflow.

Run all commands from `/root/cybergym-playground`.

## Prerequisites

- CyberPlayground server is running, for example on
  `http://127.0.0.1:10382`.
- The repo has build recipes for the sampled projects.
- For Codex runs, `codex` CLI is installed and authenticated.
- For Claude Code runs, `ccr code` is installed and authenticated.

Set the API once if you are not using the default:

```bash
export PLAYGROUND_API=http://127.0.0.1:10382
```

Check the local setup:

```bash
scripts/codex_eval.sh doctor
```

## Codex: 100-Task T0 Run

Use a unique agent id for every eval run. The timestamp keeps logs and DB tasks
separate from earlier runs.

```bash
export AGENT=codex-t0-100-$(date -u +%Y%m%d-%H%M%S)

scripts/codex_eval.sh sample \
  --count 100 \
  --seed 20260601 \
  --out /tmp/$AGENT.ids

scripts/codex_eval.sh queue "$AGENT" \
  --tier T0 \
  --ids-file /tmp/$AGENT.ids

scripts/codex_eval.sh start "$AGENT"
```

`start` launches a detached runner and writes logs under:

```text
/tmp/cyberplayground-logs/$AGENT/
```

The default launched command is:

```bash
codex -a never exec --sandbox danger-full-access --json -
```

`-a never` is placed before `exec` because it is a global Codex option. Putting
it after `exec` can fail with `unexpected argument '-a'`.

Follow the detached Codex runner:

```bash
scripts/codex_eval.sh logs "$AGENT"
```

## CCR Code: New Claude Code Task

Use this workflow when the agent under test is Claude Code via CCR Code Router.
The command is always `ccr code`; the raw CCR stream-json log is the source of
truth.

Queue one fresh T0 task:

```bash
export AGENT=ccr-t0-1-$(date -u +%Y%m%d-%H%M%S)

scripts/codex_eval.sh sample \
  --count 1 \
  --seed "$(date -u +%s)" \
  --out /tmp/$AGENT.ids

scripts/codex_eval.sh queue "$AGENT" \
  --tier T0 \
  --ids-file /tmp/$AGENT.ids
```

Start the CCR runner in terminal 1:

```bash
TASK_TIMEOUT=1800 RESULT_WAIT=180 ./scripts/run_agent.sh "$AGENT" \
  ccr code -p --permission-mode auto \
  --output-format stream-json \
  --include-partial-messages \
  --verbose
```

Start the readable sidecar in terminal 2:

```bash
scripts/codex_eval.sh pretty "$AGENT" --interval 15 --tail-lines 40
```

The runner terminal remains raw JSON. The sidecar watches the newest per-task
log under `/tmp/cyberplayground-logs/$AGENT/`, formats it locally, and writes
the full formatted view to:

```text
/tmp/cyberplayground-logs/$AGENT/runner.pretty.out
```

Use `Ctrl-C` to stop a foreground CCR runner or sidecar watcher.

## CCR Code: 100-Task T0 Run

Queue 100 sampled tasks:

```bash
export AGENT=ccr-t0-100-$(date -u +%Y%m%d-%H%M%S)

scripts/codex_eval.sh sample \
  --count 100 \
  --seed 20260601 \
  --out /tmp/$AGENT.ids

scripts/codex_eval.sh queue "$AGENT" \
  --tier T0 \
  --ids-file /tmp/$AGENT.ids
```

Run the same two-terminal workflow:

```bash
TASK_TIMEOUT=1800 RESULT_WAIT=180 ./scripts/run_agent.sh "$AGENT" \
  ccr code -p --permission-mode auto \
  --output-format stream-json \
  --include-partial-messages \
  --verbose
```

```bash
scripts/codex_eval.sh pretty "$AGENT" --interval 15 --tail-lines 80
```

To compare agents on exactly the same bug instances, keep and reuse the sampled
ids file. For example:

```bash
export OLD_IDS=/tmp/codex-t0-100-20260601-025521.ids
export AGENT=ccr-t0-100-same-as-codex-$(date -u +%Y%m%d-%H%M%S)

scripts/codex_eval.sh queue "$AGENT" \
  --tier T0 \
  --ids-file "$OLD_IDS"
```

The ids file is the benchmark manifest. If it is missing, recreate the sample
with the same `--count` and `--seed` only if the registry has not changed.

## CCR Output Tools

`scripts/run_agent.sh` does not format CCR output. It saves the raw stream in
each per-task log:

```text
/tmp/cyberplayground-logs/$AGENT/<instance>_<task>.log
```

Format one saved CCR task log after the fact:

```bash
scripts/ccr_reformat_log.sh /tmp/cyberplayground-logs/$AGENT/<task-log>.log
```

Format only the end of a large log:

```bash
CCR_REFORMAT_BYTES=500000 \
  scripts/ccr_reformat_log.sh /tmp/cyberplayground-logs/$AGENT/<task-log>.log
```

Run a one-shot refresh of the newest log for an agent:

```bash
scripts/codex_eval.sh pretty "$AGENT" --once --tail-lines 80
```

Useful sidecar options:

```bash
scripts/codex_eval.sh pretty "$AGENT" --interval 10 --tail-lines 40
scripts/codex_eval.sh pretty "$AGENT" --interval 15 --tail-lines 0
scripts/codex_eval.sh pretty "$AGENT" --bytes 500000 --timeout 30
```

`--tail-lines 0` prints the full formatted view every refresh. Smaller
`--tail-lines` values are better during long runs.

## Status And Reports

Print lightweight counters:

```bash
scripts/codex_eval.sh status "$AGENT"
```

Print the full report:

```bash
scripts/codex_eval.sh report "$AGENT"
```

For a detached Codex run, check whether the runner is alive:

```bash
scripts/codex_eval.sh pid "$AGENT"
```

Stop only a detached Codex runner process:

```bash
scripts/codex_eval.sh stop "$AGENT"
```

`stop` does not delete queued tasks or workspaces. If a task was assigned when
the runner stopped, the next runner for the same agent id will continue from
that active task through `/eval/{agent_id}/next`.

## What The Runner Does

For each queued task, `scripts/run_agent.sh`:

1. Calls `GET /eval/{agent_id}/next`.
2. Lets the server create exactly one workspace.
3. Starts a fresh agent process in that task's vulnerable source tree.
4. Sends the task prompt on stdin.
5. Saves the per-task raw transcript to
   `/tmp/cyberplayground-logs/{agent_id}/{instance}_{task}.log`.
6. Streams the agent output to `runner.out`.
7. Polls `GET /tasks/{task_id}` after the agent exits so slow server-side
   submit verification can settle.

The runner continues until `/eval/{agent_id}/next` reports no task remains.

## Important Codex Sandbox Detail

Use `--sandbox danger-full-access` for Codex benchmark runs unless you are
intentionally testing a more restricted Codex profile inside an isolated VM or
container.

With `--sandbox workspace-write`, nested Codex command executions can run with
network disabled. In this setup that means the agent may find a valid bug but
fail to call the local API with errors like:

```text
curl: (7) Couldn't connect to server
```

The host can still reach `127.0.0.1:10382`; the failure is inside the nested
Codex sandbox. If you see this, restart future Codex runs with:

```bash
CODEX_SANDBOX=danger-full-access scripts/codex_eval.sh start "$AGENT"
```

Do not restart an active run just to change the sandbox unless you are prepared
to handle the currently assigned workspace/task.

## Timeouts

Defaults:

- `TASK_TIMEOUT=1800`: maximum wall time for one agent process.
- `RESULT_WAIT=180`: seconds to keep polling task status after the agent exits.

Submit scoring can take tens of seconds or more because the server builds and
runs both vulnerable and fixed binaries. Increase these values for slow projects:

```bash
TASK_TIMEOUT=2700 RESULT_WAIT=300 scripts/codex_eval.sh start "$AGENT"
```

For CCR, set the same variables on the manual runner command:

```bash
TASK_TIMEOUT=2700 RESULT_WAIT=300 ./scripts/run_agent.sh "$AGENT" \
  ccr code -p --permission-mode auto \
  --output-format stream-json \
  --include-partial-messages \
  --verbose
```

## Sampling Options

Sample from all registry-compatible instance JSON files:

```bash
scripts/codex_eval.sh sample --count 100 --seed 1 --out /tmp/sample.ids
```

Sample from one project:

```bash
scripts/codex_eval.sh sample --count 10 --project expat --seed 1
```

Show the sampled project beside each id:

```bash
scripts/codex_eval.sh sample --count 10 --seed 1 --with-project
```

The sampler skips `projects.json`, AppleDouble `._*.json` files, and JSON files
that do not contain registry-style instances.

## Existing Results

Captured result snapshots live under [`docs/results/`](results/).

The stopped Codex T0 100-task run is documented here:

```text
docs/results/codex-t0-100-20260601-025521.md
```

## Common Checks

There is no `/tasks/{task_id}/status` endpoint. Use:

```bash
curl -s "$PLAYGROUND_API/tasks/$TASK_ID" | python3 -m json.tool
```

To see pending counts:

```bash
curl -s "$PLAYGROUND_API/eval/$AGENT/pending" | python3 -m json.tool
```

To manually queue without the wrapper:

```bash
python3 scripts/run_eval.py \
  --agent-id "$AGENT" \
  --tier T0 \
  --no-launch \
  --instance-ids $(tr '\n' ' ' < /tmp/$AGENT.ids)
```

Prefer the wrapper for normal use because it preserves the command, pid file,
and log layout in one place.
