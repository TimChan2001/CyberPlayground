#!/usr/bin/env python3
"""Reformat a CCR Code / Claude Code stream-json CyberPlayground task log."""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path


COLORS = {
    "reset": "\033[0m",
    "dim": "\033[90m",
    "bold": "\033[1m",
    "agent": "\033[36m",
    "bash": "\033[35m",
    "read": "\033[36m",
    "grep": "\033[35m",
    "write": "\033[34m",
    "web": "\033[36m",
    "tool": "\033[35m",
    "result": "\033[90m",
    "api": "\033[33m",
    "error": "\033[90m",
    "path": "\033[90m",
}

# ── Helpers ──────────────────────────────────────────────────────────────────

def parse_line(raw_line: str):
    """Parse a single log line, returning (line_type, obj) or None."""
    line = raw_line.strip()
    if not line:
        return None
    # Strip the line-number prefix from `cat -n` output if present
    line = re.sub(r"^\s*\d+\t", "", line)
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        return None
    return obj


def short_path(p: str, ws: str = "") -> str:
    """Shorten workspace paths. Tries to strip the workspace prefix first."""
    if ws and p.startswith(ws):
        rel = p[len(ws):].lstrip("/") or "."
        return rel
    # If the path contains the workspace dir name, strip up to it
    ws_name = os.path.basename(ws.rstrip("/")) if ws else ""
    if ws_name and ws_name in p:
        idx = p.index(ws_name) + len(ws_name)
        rel = p[idx:].lstrip("/") or "."
        return rel
    # Collapse long absolute paths: keep last 3 components
    parts = p.split("/")
    if len(parts) > 5:
        return "/".join(parts[-3:])
    return p


def short_command(cmd: str, ws: str = "") -> str:
    """Shorten workspace paths inside a shell command without dropping the command."""
    if not ws:
        return cmd
    workspace = ws.rstrip("/")
    display = cmd.replace(workspace + "/", "")
    display = display.replace(workspace, ".")
    return re.sub(r"\s+", " ", display).strip()


def summarize_content(content: str, max_len: int = 200) -> str:
    """Summarize tool result content."""
    if not isinstance(content, str):
        return ""
    c = content.replace("\n", " ").strip()
    if len(c) > max_len:
        return c[:max_len] + "…"
    return c


def one_line(text: str, max_len: int = 180) -> str:
    text = re.sub(r"\s+", " ", str(text)).strip()
    if len(text) > max_len:
        return text[: max_len - 1].rstrip() + "…"
    return text


def colorize(text: str, color: str, enabled: bool) -> str:
    if not enabled:
        return text
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def lowkey(text: str, enabled: bool) -> str:
    return colorize(text, "dim", enabled)


def extract_workspace(lines_obj: list) -> str:
    """Extract workspace directory from init event."""
    for obj in lines_obj:
        if obj.get("type") == "system" and obj.get("subtype") == "init":
            return obj.get("cwd", "")
    return ""


# ── Core: extract events ─────────────────────────────────────────────────────

def extract_events(parsed_lines: list, ws: str) -> list:
    """
    Walk the parsed JSON lines and emit a chronological list of
    high-level events suitable for formatting.
    """
    events = []

    for i, obj in enumerate(parsed_lines):
        t = obj.get("type", "")
        sub = obj.get("subtype", "")

        # ── Init ─────────────────────────────────────────────────────
        if t == "system" and sub == "init":
            events.append({
                "kind": "init",
                "session_id": obj.get("session_id", ""),
                "model": obj.get("model", ""),
                "cwd": obj.get("cwd", ""),
            })

        # ── Assistant message (complete, with tool calls) ────────────
        elif t == "assistant":
            msg = obj.get("message", {})
            content = msg.get("content", [])
            for block in content:
                if block.get("type") == "tool_use":
                    tool_id = block.get("id", "")
                    name = block.get("name", "")
                    inp = block.get("input", {})
                    events.append({
                        "kind": "tool_call",
                        "tool": name,
                        "tool_id": tool_id,
                        "input": inp,
                        "line": i,
                        "ws": ws,
                    })
                elif block.get("type") == "text":
                    text = block.get("text", "")
                    if len(text.strip()) > 40:
                        events.append({
                            "kind": "agent_text",
                            "text": text,
                            "line": i,
                        })

        # ── User message = tool results ──────────────────────────────
        elif t == "user":
            msg = obj.get("message", {})
            content = msg.get("content", [])
            for block in content:
                if block.get("type") == "tool_result":
                    tool_id = block.get("tool_use_id", "")
                    result_content = block.get("content", "")
                    is_error = block.get("is_error", False)

                    events.append({
                        "kind": "tool_result",
                        "tool_id": tool_id,
                        "content": result_content,
                        "structured_result": obj.get("tool_use_result"),
                        "is_error": is_error,
                        "line": i,
                        "ws": ws,
                    })

        # ── System task events ───────────────────────────────────────
        elif t == "system" and sub == "task_notification":
            events.append({
                "kind": "task_notification",
                "task_id": obj.get("task_id", ""),
                "status": obj.get("status", ""),
                "summary": obj.get("summary", ""),
                "line": i,
            })

        elif t == "system" and sub == "task_progress":
            desc = obj.get("description", "")
            subagent = obj.get("subagent_type", "")
            usage = obj.get("usage", {})
            tool_uses = usage.get("tool_uses", 0) if isinstance(usage, dict) else 0
            duration = usage.get("duration_ms", 0) if isinstance(usage, dict) else 0
            if tool_uses > 0 and tool_uses % 10 == 0:
                events.append({
                    "kind": "subagent_progress",
                    "description": desc,
                    "tool_uses": tool_uses,
                    "duration_s": round(duration / 1000, 1),
                    "subagent_type": subagent,
                    "line": i,
                })

    return events


# ── Format events to markdown ────────────────────────────────────────────────

def format_tool_call(ev: dict) -> str:
    name = ev["tool"]
    inp = ev["input"]
    ws = ev.get("ws", "")

    if name == "Bash":
        cmd = inp.get("command", "")
        desc = inp.get("description", "")
        display_cmd = short_command(cmd, ws)
        if len(display_cmd) > 200:
            display_cmd = display_cmd[:197] + "…"
        if "curl" in cmd and "10382" in cmd:
            if "/identify" in cmd:
                return f"**API → /identify**  \n`{display_cmd[:200]}`"
            if "/submit" in cmd:
                return f"**API → /submit**  \n`{display_cmd[:200]}`"
            if "/hint" in cmd:
                return f"**API → /hint**  \n`{display_cmd[:200]}`"
            if "/build_recipes" in cmd:
                match = re.search(r"/build_recipes/([A-Za-z0-9_.-]+)", cmd)
                project = match.group(1) if match else "<project>"
                return f"**API → /build_recipes/{project}**"
        if desc:
            return f"**Bash:** {desc}  \n`{display_cmd}`"
        return f"**Bash:** `{display_cmd}`"

    elif name == "Read":
        fp = short_path(inp.get("file_path", ""), ws)
        off = inp.get("offset", "")
        lim = inp.get("limit", "")
        rng = f"L{off}" + (f"–{int(off)+int(lim)}" if lim else "+") if off else "full"
        return f"**Read:** `{fp}` ({rng})"

    elif name == "Grep":
        pat = inp.get("pattern", "")[:60]
        path = short_path(inp.get("path", ""), ws)
        return f"**Grep:** `{pat}` in `{path}`"

    elif name == "WebSearch":
        q = inp.get("query", "")[:120]
        return f"**WebSearch:** `{q}`"

    elif name == "WebFetch":
        url = inp.get("url", "")[:120]
        return f"**WebFetch:** `{url}`"

    elif name == "Agent":
        desc = inp.get("description", "")[:80]
        sub = inp.get("subagent_type", "")
        return f"**Agent** ({sub}): {desc}"

    elif name == "Glob":
        pat = inp.get("pattern", "")
        path = short_path(inp.get("path", ""), ws)
        return f"**Glob:** `{pat}` in `{path}`"

    elif name == "Write":
        fp = short_path(inp.get("file_path", ""), ws)
        return f"**Write:** `{fp}`"

    elif name == "Edit":
        fp = short_path(inp.get("file_path", ""), ws)
        return f"**Edit:** `{fp}`"

    else:
        keys = list(inp.keys())[:5]
        return f"**{name}:** keys={keys}"


def format_tool_result(ev: dict) -> str:
    content = ev.get("content", "")
    ws = ev.get("ws", "")
    structured = ev.get("structured_result")

    if isinstance(structured, dict):
        file_result = structured.get("file")
        if isinstance(file_result, dict):
            path = short_path(str(file_result.get("filePath") or ""), ws)
            start = file_result.get("startLine")
            num_lines = file_result.get("numLines")
            total = file_result.get("totalLines")
            if isinstance(start, int) and isinstance(num_lines, int) and num_lines > 0:
                end = start + num_lines - 1
                total_text = f" of {total}" if total else ""
                return f"*Read result: `{path}` L{start}–L{end}, {num_lines} lines{total_text}*"
            return f"*Read result: `{path}`*"

        stdout = structured.get("stdout")
        stderr = structured.get("stderr")
        if isinstance(stdout, str) and stdout.strip():
            content = stdout
        elif isinstance(stderr, str) and stderr.strip():
            content = stderr

    if not isinstance(content, str):
        return "*<non-text result>*"

    # API JSON responses
    if content.strip().startswith("{"):
        try:
            parsed = json.loads(content)
            if "status" in parsed or "fix_source_dir" in parsed or "hint" in parsed:
                return f"**API Response:** `{json.dumps(parsed)[:300]}`"
            if "task_id" in parsed:
                return f"**API Response:** `{json.dumps(parsed)[:300]}`"
        except json.JSONDecodeError:
            pass

    # Task briefing
    if content.strip().startswith("# Vulnerability"):
        return "*<Task briefing received>*"

    # Build recipe
    if "#!/usr/bin/env bash" in content[:50]:
        return "*<Build recipe received>*"

    # Heredoc / large Bash output
    if content.count("\n") > 15 and not any(k in content[:200] for k in ["{", "case ", "static ", "L1\t"]):
        lines = [l.strip() for l in content.strip().split("\n") if l.strip()]
        return f"*<{len(lines)} lines of output>*"

    # Grep results
    if re.match(r"^/.+:\d+[:\-]", content.strip()[:200]):
        lines = content.strip().split("\n")
        if len(lines) <= 3:
            short = summarize_content(content, 250)
            return f"`{short}`"
        return f"*{len(lines)} grep match(es)*"

    # Read results (numbered lines)
    if re.match(r"^\d+\t", content.strip()[:20]):
        lines = content.strip().split("\n")
        first_num = re.match(r"(\d+)", lines[0])
        last_num = re.match(r"(\d+)", lines[-1]) if len(lines) > 1 else first_num
        rng = f"L{first_num.group(1)}"
        if last_num and last_num.group(1) != first_num.group(1):
            rng += f"–{last_num.group(1)}"
        return f"*Read result: {rng}, {len(lines)} lines*"

    short = summarize_content(content, 200)
    return f"`{short}`"


# Phase progression order — once entered, we only move forward
PHASE_ORDER = [
    "Reconnaissance",
    "Source Audit",
    "CVE Research",
    "Build & Local Testing",
    "Exploit Crafting",
    "Deep Investigation (Subagent)",
]
PHASE_INDEX = {name: i for i, name in enumerate(PHASE_ORDER)}

PHASE_KEYWORDS = [
    # (keywords, phase_name)  — checked in order, first match wins
    (["reconnaissance", "initial", "list source", "directory contents"], "Reconnaissance"),
    (["audit", "thorough", "security review", "look at the key area", "look more carefully"], "Source Audit"),
    (["cve", "known vulnerability", "search for known"], "CVE Research"),
    (["build", "compile", "asan", "cmake"], "Build & Local Testing"),
    (["craft", "exploit", "poc", "proof-of-concept", "mutate", "malformed"], "Exploit Crafting"),
    (["subagent", "search for subtle", "deep investigation"], "Deep Investigation (Subagent)"),
]

def detect_phase(agent_text: str, current_phase: str = "") -> str:
    """Heuristic: detect which phase the agent is in. Only advances forward."""
    t = agent_text.lower()
    for keywords, phase_name in PHASE_KEYWORDS:
        if any(k in t for k in keywords):
            # Only advance to a later phase, never go backwards
            if current_phase and PHASE_INDEX.get(phase_name, 0) <= PHASE_INDEX.get(current_phase, 0):
                return current_phase
            return phase_name
    return current_phase


def format_tool_result_label(call: dict) -> str:
    """Compact label for a tool result when results arrive after batched calls."""
    name = call.get("tool", "Tool")
    inp = call.get("input", {})
    ws = call.get("ws", "")

    if name == "Read":
        return f"Read `{short_path(str(inp.get('file_path', '')), ws)}`"
    if name == "Bash":
        desc = inp.get("description")
        if desc:
            return f"Bash {desc}"
        cmd = short_command(str(inp.get("command", "")), ws)
        return f"Bash `{cmd[:80]}`"
    if name == "Grep":
        return f"Grep `{str(inp.get('pattern', ''))[:60]}`"
    if name == "Write":
        return f"Write `{short_path(str(inp.get('file_path', '')), ws)}`"
    if name == "Edit":
        return f"Edit `{short_path(str(inp.get('file_path', '')), ws)}`"
    return str(name)


def format_events(events: list, ws: str) -> str:
    """Convert events to a Markdown document with phase grouping."""
    sections = []
    sections.append("# CyberPlayground Task Log — Reformatted\n")
    calls_by_id = {
        e.get("tool_id"): e
        for e in events
        if e.get("kind") == "tool_call" and e.get("tool_id")
    }

    # ── Session metadata ─────────────────────────────────────────────
    init_ev = next((e for e in events if e["kind"] == "init"), None)
    if init_ev:
        sections.append("## Session\n")
        sections.append(f"- **Session ID:** `{init_ev['session_id']}`")
        sections.append(f"- **Model:** {init_ev['model']}")
        sections.append(f"- **Workspace:** `{init_ev['cwd']}`")
        sections.append("")

    # ── Task briefing ────────────────────────────────────────────────
    briefing = next(
        (e for e in events if e["kind"] == "tool_result"
         and isinstance(e.get("content"), str)
         and e["content"].strip().startswith("# Vulnerability")),
        None,
    )
    if briefing:
        sections.append("## Task Briefing\n")
        c = briefing["content"]
        task_id_m = re.search(r"\*\*Task ID\*\*:\s*(\S+)", c)
        project_m = re.search(r"\*\*Project\*\*:\s*(\S+)", c)
        hint_m = re.search(r"\*\*Hint\*\*:\s*(.+?)(?:\n|$)", c)
        if task_id_m:
            sections.append(f"- **Task ID:** `{task_id_m.group(1)}`")
        if project_m:
            sections.append(f"- **Project:** {project_m.group(1)}")
        if hint_m:
            sections.append(f"- **Hint:** {hint_m.group(1).strip()}")
        sections.append("")

    # ── Chronological account with phase grouping ────────────────────
    sections.append("## Chronological Account\n")

    # Group events into phases based on agent_text boundaries
    phases = []  # list of (phase_title, events_in_phase)
    current_phase = "Reconnaissance"
    current_events = []

    for ev in events:
        kind = ev["kind"]

        if kind == "agent_text":
            detected = detect_phase(ev["text"], current_phase)
            if detected and detected != current_phase:
                # Flush current phase
                if current_events:
                    phases.append((current_phase, current_events))
                current_phase = detected
                current_events = []
            # Always include agent text in current phase events
            current_events.append(ev)
        else:
            current_events.append(ev)

    # Flush remaining
    if current_events:
        phases.append((current_phase, current_events))

    # Format each phase
    for phase_title, phase_events in phases:
        sections.append(f"### {phase_title}\n")

        step = 0
        for ev in phase_events:
            kind = ev["kind"]

            # Agent text
            if kind == "agent_text":
                text = ev["text"].strip()
                if len(text) > 40:
                    if len(text) > 500:
                        text = text[:500] + "…"
                    sections.append(f"> **Agent:** {text}\n")
                continue

            # Tool call
            if kind == "tool_call":
                step += 1
                sections.append(f"**{step}.** {format_tool_call(ev)}")
                continue

            # Tool result
            if kind == "tool_result":
                result = format_tool_result(ev)
                call = calls_by_id.get(ev.get("tool_id"))
                if call:
                    sections.append(f"   ↳ **Result for {format_tool_result_label(call)}:** {result}")
                else:
                    sections.append(f"   ↳ {result}")
                continue

            # Task notification
            if kind == "task_notification":
                sections.append(
                    f"   📋 **Task Notification:** {ev.get('summary', '')} "
                    f"(status={ev.get('status', '')})"
                )
                continue

            # Subagent progress
            if kind == "subagent_progress":
                sections.append(
                    f"   ⏳ *Subagent: {ev.get('description', '')} "
                    f"({ev.get('tool_uses', 0)} tools, "
                    f"{ev.get('duration_s', 0)}s)*"
                )
                continue

        sections.append("")

    # ── Milestone summary ────────────────────────────────────────────
    sections.append("## Milestone Summary\n")

    identify_calls = [e for e in events if e["kind"] == "tool_call"
                      and e["tool"] == "Bash"
                      and "/identify" in e.get("input", {}).get("command", "")]
    submit_calls = [e for e in events if e["kind"] == "tool_call"
                    and e["tool"] == "Bash"
                    and "/submit" in e.get("input", {}).get("command", "")]
    hint_calls = [e for e in events if e["kind"] == "tool_call"
                  and e["tool"] == "Bash"
                  and "/hint" in e.get("input", {}).get("command", "")]

    sections.append(f"| Milestone | Status |")
    sections.append(f"|-----------|--------|")
    sections.append(f"| Hint requested | {'✅ ' + str(len(hint_calls)) + '×' if hint_calls else '❌ Not requested'} |")
    sections.append(f"| Identification (`/identify`) | {'✅ ' + str(len(identify_calls)) + '×' if identify_calls else '❌ Not attempted'} |")
    sections.append(f"| Submission (`/submit`) | {'✅ ' + str(len(submit_calls)) + '×' if submit_calls else '❌ Not attempted'} |")

    # Count tool calls by type
    tool_counts = defaultdict(int)
    for e in events:
        if e["kind"] == "tool_call":
            tool_counts[e["tool"]] += 1
    if tool_counts:
        sections.append("")
        sections.append("**Tool usage:** " + ", ".join(
            f"{k}×{v}" for k, v in sorted(tool_counts.items(), key=lambda x: -x[1])
        ))

    sections.append("")
    return "\n".join(sections)


def compact_tool_call(ev: dict, colors: bool) -> str:
    name = ev.get("tool", "Tool")
    inp = ev.get("input", {})
    ws = ev.get("ws", "")

    if name == "Bash":
        cmd = short_command(str(inp.get("command", "")), ws)
        desc = str(inp.get("description", "")).strip()
        if "curl" in cmd and "10382" in cmd:
            endpoint = "/api"
            for candidate in ["/identify", "/submit", "/hint", "/build_recipes"]:
                if candidate in cmd:
                    endpoint = candidate
                    break
            return f"{colorize('api', 'api', colors)} {lowkey(endpoint, colors)} {lowkey(one_line(cmd, 140), colors)}"
        label = desc or one_line(cmd, 80)
        return f"{colorize('bash', 'bash', colors)} {lowkey(label + ':', colors)} {lowkey(one_line(cmd, 160), colors)}"

    if name == "Read":
        path = short_path(str(inp.get("file_path", "")), ws)
        off = inp.get("offset")
        limit = inp.get("limit")
        if off:
            rng = f" L{off}" + (f"-{int(off) + int(limit) - 1}" if limit else "+")
        else:
            rng = ""
        return f"{colorize('read', 'read', colors)} {lowkey(path + rng, colors)}"

    if name == "Grep":
        pattern = str(inp.get("pattern") or inp.get("query") or "")
        path = short_path(str(inp.get("path") or inp.get("glob") or "."), ws)
        return f"{colorize('grep', 'grep', colors)} {lowkey(f'`{pattern}` in `{path}`', colors)}"

    if name == "Glob":
        pattern = str(inp.get("pattern") or "")
        path = short_path(str(inp.get("path") or "."), ws)
        return f"{colorize('glob', 'tool', colors)} {lowkey(f'`{pattern}` in `{path}`', colors)}"

    if name in {"Write", "Edit"}:
        path = short_path(str(inp.get("file_path", "")), ws)
        color = "write" if name == "Write" else "tool"
        return f"{colorize(name.lower(), color, colors)} {lowkey(path, colors)}"

    if name in {"WebSearch", "WebFetch"}:
        value = inp.get("query") or inp.get("url") or ""
        return f"{colorize(name.lower(), 'web', colors)} {lowkey(one_line(value, 160), colors)}"

    if name in {"Agent", "Task"}:
        desc = inp.get("description") or inp.get("prompt") or inp.get("subagent_type") or ""
        return f"{colorize('agent', 'agent', colors)} {lowkey(one_line(desc, 140), colors)}"

    return f"{colorize(name.lower(), 'tool', colors)} {lowkey(one_line(inp, 140), colors)}"


def result_text(ev: dict) -> str:
    structured = ev.get("structured_result")
    if isinstance(structured, dict):
        file_result = structured.get("file")
        if isinstance(file_result, dict):
            return str(file_result.get("content") or "")
        for key in ("content", "stdout", "stderr", "error"):
            value = structured.get(key)
            if isinstance(value, str) and value:
                return value
    content = ev.get("content")
    return content if isinstance(content, str) else ""


def compact_result(call: dict | None, ev: dict, colors: bool) -> list[str]:
    tool = call.get("tool") if call else ""
    ws = ev.get("ws", "")
    text = result_text(ev)
    structured = ev.get("structured_result")
    prefix = lowkey("  ->", colors)

    if ev.get("is_error"):
        return [lowkey(f"  ! {one_line(text, 180)}", colors)]

    if tool == "Read" and isinstance(structured, dict):
        file_result = structured.get("file")
        if isinstance(file_result, dict):
            path = short_path(str(file_result.get("filePath") or ""), ws)
            start = file_result.get("startLine")
            count = file_result.get("numLines")
            total = file_result.get("totalLines")
            if isinstance(start, int) and isinstance(count, int) and count > 0:
                end = start + count - 1
                suffix = f" of {total}" if total else ""
                return [lowkey(f"  -> {path} lines {start}-{end} ({count}{suffix})", colors)]
            return [lowkey(f"  -> {path}", colors)]

    if tool == "Grep":
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            return [f"{prefix} no matches"]
        call_path = ""
        if call:
            call_path = short_path(
                str((call.get("input") or {}).get("path") or (call.get("input") or {}).get("glob") or ""),
                ws,
            )
        rendered = []
        for line in lines[:5]:
            match = re.match(r"(.+?):(\d+)(?::|-)(.*)", line)
            if match:
                path = short_path(match.group(1), ws)
                rendered.append(
                    lowkey(f"  -> {path} line {match.group(2)}: {one_line(match.group(3), 120)}", colors)
                )
                continue
            match = re.match(r"(\d+)(?::|-)(.*)", line)
            if match and call_path:
                rendered.append(
                    lowkey(f"  -> {call_path} line {match.group(1)}: {one_line(match.group(2), 120)}", colors)
                )
            else:
                rendered.append(lowkey(f"  -> {one_line(line, 160)}", colors))
        if len(lines) > 5:
            rendered.append(lowkey(f"  -> ... {len(lines) - 5} more matches", colors))
        return rendered

    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            if "verdict" in data:
                return [lowkey(f"  -> verdict={data.get('verdict')} task={data.get('task_id', '')}", colors)]
            if "status" in data:
                return [lowkey(f"  -> status={data.get('status')} task={data.get('task_id', '')}", colors)]
            if "hint" in data:
                return [lowkey(f"  -> hint: {one_line(data.get('hint', ''), 160)}", colors)]
            if "task_id" in data:
                return [lowkey(f"  -> {one_line(json.dumps(data), 180)}", colors)]
        except json.JSONDecodeError:
            pass

    if stripped.startswith("# Vulnerability"):
        return [lowkey("  -> task briefing", colors)]
    if stripped.startswith("#!/usr/bin/env bash"):
        return [lowkey("  -> build recipe", colors)]

    lines = [line for line in stripped.splitlines() if line.strip()]
    if len(lines) > 8:
        return [lowkey(f"  -> {len(lines)} lines: {one_line(lines[0], 140)}", colors)]
    if not lines:
        return []
    return [lowkey(f"  -> {one_line(' | '.join(lines), 180)}", colors)]


def format_compact_events(
    events: list,
    ws: str,
    script_start: str | None = None,
    script_end: str | None = None,
    exit_code: int | None = None,
    colors: bool = False,
) -> str:
    calls_by_id = {
        e.get("tool_id"): e
        for e in events
        if e.get("kind") == "tool_call" and e.get("tool_id")
    }

    lines = []
    init_ev = next((e for e in events if e["kind"] == "init"), None)
    if init_ev:
        lines.append(
            lowkey(
                f"session model={init_ev.get('model', '')} workspace={short_path(init_ev.get('cwd', ''), ws)}",
                colors,
            )
        )
    if script_start or script_end or exit_code is not None:
        bits = []
        if script_start:
            start_clean = re.sub(r"\[.*?\]", "", script_start).strip()
            bits.append(f"start={start_clean}")
        if script_end:
            end_ts = re.sub(r"^Script done on ", "", script_end)
            end_clean = re.sub(r"\[.*?\]", "", end_ts).strip()
            bits.append(f"end={end_clean}")
        if exit_code is not None:
            bits.append(f"exit={exit_code}")
        lines.append(lowkey(f"timing {' '.join(bits)}", colors))

    last_agent = ""

    def add_blank() -> None:
        if lines and lines[-1] != "":
            lines.append("")

    for ev in events:
        kind = ev.get("kind")

        if kind == "init":
            continue

        if kind == "agent_text":
            text = one_line(ev.get("text", ""), 260)
            if text and text != last_agent:
                add_blank()
                lines.append(f"{colorize('agent', 'agent', colors)} {lowkey(text, colors)}")
                last_agent = text
            continue

        if kind == "tool_call":
            add_blank()
            lines.append(compact_tool_call(ev, colors))
            continue

        if kind == "tool_result":
            call = calls_by_id.get(ev.get("tool_id"))
            lines.extend(compact_result(call, ev, colors))
            continue

        if kind == "task_notification":
            summary = ev.get("summary") or ev.get("status") or ""
            add_blank()
            lines.append(f"{colorize('task', 'api', colors)} {lowkey(one_line(summary, 160), colors)}")
            continue

        if kind == "subagent_progress":
            add_blank()
            progress = f"({ev.get('tool_uses', 0)} tools, {ev.get('duration_s', 0)}s)"
            lines.append(
                f"{colorize('subagent', 'agent', colors)} "
                f"{lowkey(one_line(ev.get('description', ''), 120), colors)} "
                f"{lowkey(progress, colors)}"
            )

    return "\n".join(lines).rstrip() + "\n"


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Reformat a CCR Code / Claude Code stream-json task log."
    )
    parser.add_argument("log_file")
    parser.add_argument("output_file", nargs="?")
    parser.add_argument(
        "--style",
        choices=("compact", "markdown"),
        default="compact",
        help="output style, default compact",
    )
    parser.add_argument(
        "--color",
        choices=("auto", "always", "never"),
        default="auto",
        help="ANSI color mode for compact output",
    )
    args = parser.parse_args()

    log_path = args.log_file
    if args.output_file:
        out_path = args.output_file
    else:
        base = Path(log_path).stem
        suffix = "_reformatted.md" if args.style == "markdown" else "_compact.txt"
        out_path = str(Path(log_path).parent / f"{base}{suffix}")

    # Parse all lines
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        raw_lines = f.readlines()

    parsed = []
    script_start = None
    script_end = None
    exit_code = None

    for raw in raw_lines:
        raw_stripped = raw.strip()
        # Detect script start/end markers
        if raw_stripped.startswith("Script started on "):
            script_start = raw_stripped.replace("Script started on ", "")
            continue
        if raw_stripped.startswith("Script done on "):
            script_end = raw_stripped
            m = re.search(r'COMMAND_EXIT_CODE="(\d+)"', raw_stripped)
            if m:
                exit_code = int(m.group(1))
            continue

        obj = parse_line(raw_stripped)
        if obj is not None:
            parsed.append(obj)

    ws = extract_workspace(parsed)
    events = extract_events(parsed, ws)
    if args.style == "markdown":
        output = format_events(events, ws)
    else:
        color_enabled = args.color == "always" or (
            args.color == "auto" and sys.stdout.isatty()
        )
        output = format_compact_events(
            events,
            ws,
            script_start=script_start,
            script_end=script_end,
            exit_code=exit_code,
            colors=color_enabled,
        )

    # Prepend session timing info
    header = ""
    if args.style == "markdown" and (script_start or script_end):
        header += "## Session Timing\n"
        if script_start:
            # Clean up the start timestamp
            start_clean = re.sub(r'\[.*?\]', '', script_start).strip()
            header += f"- **Start:** {start_clean}\n"
        if script_end:
            # Extract just the timestamp from "Script done on ..."
            end_ts = re.sub(r'^Script done on ', '', script_end)
            end_clean = re.sub(r'\[.*?\]', '', end_ts).strip()
            header += f"- **End:** {end_clean}\n"
        if exit_code is not None:
            sig_msg = ""
            if exit_code == 130:
                sig_msg = " (SIGINT / Ctrl+C)"
            elif exit_code == 137:
                sig_msg = " (SIGKILL)"
            header += f"- **Exit code:** {exit_code}{sig_msg}\n"
        # Compute duration if both timestamps parseable
        if script_start and script_end:
            try:
                from datetime import datetime
                s = re.sub(r'\[.*?\]', '', script_start).strip()
                e_ts = re.sub(r'^Script done on ', '', script_end)
                e = re.sub(r'\[.*?\]', '', e_ts).strip()
                # Try common formats
                for fmt in ["%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S"]:
                    try:
                        sd = datetime.strptime(s, fmt)
                        ed = datetime.strptime(e, fmt)
                        dur = ed - sd
                        mins = int(dur.total_seconds() // 60)
                        header += f"- **Duration:** ~{mins} minutes\n"
                        break
                    except ValueError:
                        continue
            except Exception:
                pass
        header += "\n"

    if header:
        # Insert after the title
        parts = output.split("\n", 2)
        output = parts[0] + "\n\n" + header + parts[2] if len(parts) > 2 else output + "\n" + header

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(output)

    print(f"Written: {out_path}")


if __name__ == "__main__":
    main()
