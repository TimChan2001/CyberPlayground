#!/usr/bin/env python3
"""
Reformat a CCR / Claude Code stream-json (JSONL) task log for human reading.

Usage:
    python3 ccr_reformat_log.py <log.jsonl >log-summary.md
    python3 ccr_reformat_log.py log.jsonl

Rules applied:
  - Do not solve the vulnerability task; only reformat.
  - Do not invent events or results.
  - Preserve chronology.
  - Skip partial JSON objects at the start of the file.
  - For Read/file results: show path, line range (if present), one-line summary.
  - For Bash results: show command, summarize stdout/stderr.
  - For Grep results: show pattern, match count, key matches (≤5).
  - For WebSearch/WebFetch: show query/url and summary of results.
  - Identify attempts to identify/submit vulnerability.
  - Note final status.
"""

import json
import sys
import textwrap
from pathlib import Path

# ── Helpers ──────────────────────────────────────────────────────────────────

def compact_content(content_blocks, max_lines=6):
    """Extract a one-line summary from tool_result content blocks."""
    if not content_blocks:
        return "(empty)"
    text = ""
    for block in content_blocks:
        if isinstance(block, str):
            text += block
        elif isinstance(block, dict):
            text += block.get("text", "")
    lines = text.strip().splitlines()
    if not lines:
        return "(empty)"
    # Check for file-content style (line-numbered)
    if len(lines) > max_lines:
        first = lines[0].strip()[:120]
        last = lines[-1].strip()[:120]
        return f"{first} … ({len(lines)} lines) … {last}"
    return "; ".join(l.strip()[:100] for l in lines[:max_lines])


def extract_file_range(content_text):
    """Try to extract file path and line range from numbered content."""
    lines = content_text.strip().splitlines()
    if not lines:
        return None, None
    first_line = lines[0].strip()
    last_line = lines[-1].strip()
    # Lines look like: "1\t/* Copyright..." or "2278\t            dist_remaining"
    first_num = last_num = None
    try:
        first_num = int(first_line.split("\t")[0])
    except (ValueError, IndexError):
        pass
    try:
        last_num = int(last_line.split("\t")[0])
    except (ValueError, IndexError):
        pass
    return first_num, last_num


def summarize_read_result(content_text):
    """Produce a one-line summary of a Read tool result."""
    lines = content_text.strip().splitlines()
    first_num, last_num = extract_file_range(content_text)
    # Try to find key identifiers: struct names, function names, #defines
    key_terms = []
    for line in lines:
        s = line.strip()
        # Remove line number prefix
        if "\t" in s:
            s = s.split("\t", 1)[1] if "\t" in s else s
        s = s.strip()
        if s.startswith("typedef struct") or s.startswith("struct "):
            name = s.rstrip("{").strip().split()[-1] if "{" in s else ""
            if name:
                key_terms.append(f"struct {name}")
        elif s.startswith("static ") and "(" in s:
            fname = s.split("(")[0].strip().split()[-1]
            key_terms.append(fname)
        elif s.startswith("#define ") and len(s.split()) >= 2:
            macro = s.split()[1]
            if macro.isupper() and len(macro) > 3:
                key_terms.append(macro)
    range_str = f"L{first_num}–L{last_num}" if first_num and last_num else f"({len(lines)} lines)"
    if key_terms:
        unique = list(dict.fromkeys(key_terms))[:5]
        return f"{range_str} — {', '.join(unique)}"
    return range_str


def summarize_grep_result(content_text):
    """Summarize Grep results: count + first few matches."""
    lines = content_text.strip().splitlines()
    if not lines:
        return "No matches"
    count = len(lines)
    samples = []
    for line in lines[:4]:
        # format: /path/to/file:linenum:content  or  /path/to/file:content
        parts = line.split(":", 2)
        if len(parts) >= 3:
            fname = parts[0].rsplit("/", 1)[-1] if "/" in parts[0] else parts[0]
            samples.append(f"{fname}:{parts[1]}")
        elif len(parts) == 2:
            fname = parts[0].rsplit("/", 1)[-1] if "/" in parts[0] else parts[0]
            samples.append(fname)
    more = f" (+{count - 4} more)" if count > 4 else ""
    return f"{count} match{'es' if count != 1 else ''}: {', '.join(samples)}{more}"


def summarize_bash_result(content_text):
    """Summarize Bash output."""
    lines = content_text.strip().splitlines()
    if not lines:
        return "(no output)"
    if len(lines) <= 3:
        return "; ".join(l.strip()[:120] for l in lines)
    first = lines[0].strip()[:120]
    return f"{first} … ({len(lines)} lines)"


# ── Main Parser ──────────────────────────────────────────────────────────────

def parse_log(jsonl_text: str) -> list[dict]:
    """Parse JSONL into a list of event dicts."""
    events = []
    first_complete = False
    for i, line in enumerate(jsonl_text.splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            # Partial object at start — skip
            if not first_complete:
                continue
            # Mid-stream bad line — note it
            events.append({"type": "parse_error", "line_index": i, "snippet": line[:80]})
            continue
        first_complete = True
        events.append(obj)
    return events


def reformat_events(events: list[dict]) -> str:
    """Turn parsed events into a human-readable markdown summary."""
    out_lines = []
    session_info = {}
    tool_seq = []  # ordered list of (index, tool_name, detail, result_summary)
    pending_tool = {}  # tool_use_id → (tool_name, detail)

    # First pass: collect session info and tool calls/results
    for idx, ev in enumerate(events):
        if ev.get("type") == "parse_error":
            continue

        # Collect session metadata
        sid = ev.get("session_id", "")
        if sid and "session_id" not in session_info:
            session_info["session_id"] = sid
        sa = ev.get("subagent_type", "")
        if sa and "subagent_type" not in session_info:
            session_info["subagent_type"] = sa
        td = ev.get("task_description", "")
        if td and "task_description" not in session_info:
            session_info["task_description"] = td
        ts = ev.get("timestamp", "")
        if ts and "start_time" not in session_info:
            session_info["start_time"] = ts

        # Assistant messages contain tool_use calls
        if ev.get("type") == "assistant":
            msg = ev.get("message", {})
            model = msg.get("model", "")
            if model and "model" not in session_info:
                session_info["model"] = model
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_name = block.get("name", "?")
                        tool_id = block.get("id", "")
                        tool_input = block.get("input", {})
                        detail = format_tool_detail(tool_name, tool_input)
                        pending_tool[tool_id] = (tool_name, detail, idx)

        # User messages contain tool_results
        elif ev.get("type") == "user":
            msg = ev.get("message", {})
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        tool_id = block.get("tool_use_id", "")
                        result_content = block.get("content", "")
                        is_error = block.get("is_error", False)
                        if tool_id in pending_tool:
                            tname, detail, call_idx = pending_tool.pop(tool_id)
                            rsum = format_result_summary(tname, result_content, is_error)
                            tool_seq.append((call_idx, tname, detail, rsum))

        # task_progress events
        elif ev.get("type") == "system" and ev.get("subtype") == "task_progress":
            desc = ev.get("description", "")
            tool_uses = ev.get("usage", {}).get("tool_uses", 0)
            dur = ev.get("usage", {}).get("duration_ms", 0)
            # We just note these as section markers
            # (they'll be interleaved with tool calls chronologically)

    # Sort tool calls by their call index
    tool_seq.sort(key=lambda x: x[0])

    # Build output
    out_lines.append("# CyberPlayground Task Log — Reformatted\n")

    # Session header
    out_lines.append("## Session\n")
    out_lines.append(f"| Field | Value |")
    out_lines.append(f"|---|---|")
    for k, v in session_info.items():
        out_lines.append(f"| **{k}** | `{v}` |")
    out_lines.append("")

    # Tool call table
    out_lines.append("## Tool Call Sequence\n")
    out_lines.append("| # | Tool | Detail | Result Summary |")
    out_lines.append("|---|------|--------|----------------|")
    for i, (_, tname, detail, rsum) in enumerate(tool_seq, 1):
        # Truncate for table readability
        d = detail[:80] + ("…" if len(detail) > 80 else "")
        r = rsum[:120] + ("…" if len(rsum) > 120 else "")
        # Escape pipe chars
        d = d.replace("|", "\\|")
        r = r.replace("|", "\\|")
        out_lines.append(f"| {i} | **{tname}** | {d} | {r} |")
    out_lines.append("")

    # Detailed sections for important tool calls
    out_lines.append("## Detailed Notes\n")
    for i, (_, tname, detail, rsum) in enumerate(tool_seq, 1):
        if tname in ("Read", "Grep") and len(rsum) > 60:
            out_lines.append(f"### {i}. {tname}: {detail}")
            out_lines.append(f"→ {rsum}")
            out_lines.append("")

    # Final status
    out_lines.append("## Final Status\n")
    last_ev = events[-1] if events else {}
    if last_ev.get("type") == "parse_error":
        out_lines.append("Log ended with parse error (likely truncation).")
    else:
        out_lines.append("Log excerpt ends — session may have continued beyond captured data.")

    return "\n".join(out_lines)


def format_tool_detail(name: str, inp: dict) -> str:
    """Format the input parameters of a tool call."""
    if name == "Read":
        fp = inp.get("file_path", "?")
        # Shorten workspace prefix
        fp = fp.replace("/tmp/cyberplayground-workspaces/", "…/")
        off = inp.get("offset", "")
        lim = inp.get("limit", "")
        if off and lim:
            return f"{fp} L{off}–L{off+lim-1}"
        return fp
    elif name == "Grep":
        pat = inp.get("pattern", "?")
        path = inp.get("path", "?")
        path = path.replace("/tmp/cyberplayground-workspaces/", "…/")
        path = path.rsplit("/", 1)[-1] if "/" in path else path
        return f"`{pat}` in {path}"
    elif name == "Bash":
        cmd = inp.get("command", "?")
        return f"`{cmd[:80]}`"
    elif name == "WebSearch":
        return f'`{inp.get("query", "?")}`'
    elif name == "WebFetch":
        url = inp.get("url", "?")
        return url.replace("https://", "")[:80]
    elif name == "Glob":
        pat = inp.get("pattern", "?")
        path = inp.get("path", "")
        path = path.replace("/tmp/cyberplayground-workspaces/", "…/")
        return f"`{pat}` in {path}" if path else f"`{pat}`"
    elif name == "Write" or name == "Edit":
        fp = inp.get("file_path", "?")
        fp = fp.replace("/tmp/cyberplayground-workspaces/", "…/")
        return fp
    else:
        return str(inp)[:80]


def format_result_summary(tool_name: str, content, is_error: bool) -> str:
    """Format the result of a tool call."""
    if is_error:
        if isinstance(content, str):
            return f"🚫 ERROR: {content[:200]}"
        return "🚫 ERROR"

    # content may be a string or a list of content blocks
    text = ""
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, str):
                text += block
            elif isinstance(block, dict):
                text += block.get("text", "")
    else:
        return str(content)[:200]

    if tool_name == "Read":
        return summarize_read_result(text)
    elif tool_name == "Grep":
        return summarize_grep_result(text)
    elif tool_name == "Bash":
        return summarize_bash_result(text)
    elif tool_name == "Glob":
        lines = text.strip().splitlines()
        if not lines or text.strip() == "No files found":
            return "No files found"
        return f"{len(lines)} files: {', '.join(l.strip().rsplit('/', 1)[-1] for l in lines[:5])}"
    elif tool_name == "WebSearch":
        if not text.strip():
            return "No results"
        return f"Results returned ({len(text)} chars)"
    elif tool_name == "WebFetch":
        return compact_content([{"text": text}], max_lines=3)
    else:
        return compact_content([{"text": text}], max_lines=3)


def main():
    if len(sys.argv) > 1:
        input_text = Path(sys.argv[1]).read_text()
    else:
        input_text = sys.stdin.read()

    events = parse_log(input_text)
    output = reformat_events(events)
    print(output)


if __name__ == "__main__":
    main()
