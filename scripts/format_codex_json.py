#!/usr/bin/env python3
"""Render Codex --json event logs as readable terminal output."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Iterable, TextIO


class Renderer:
    def __init__(self) -> None:
        self._printed_commands: set[str] = set()
        self._need_blank = False

    def render_line(self, raw_line: str) -> None:
        line = raw_line.rstrip("\r\n")
        if not line:
            return

        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            self._print_plain(line)
            return

        if not isinstance(event, dict):
            self._print_plain(line)
            return

        typ = event.get("type")
        item = event.get("item")

        if typ in {"thread.started", "turn.started", "turn.completed"}:
            return

        if isinstance(item, dict):
            self._render_item_event(typ, item)
            return

        message = event.get("message") or event.get("text")
        if message:
            self._print_section("Event", str(message))

    def _render_item_event(self, event_type: str | None, item: dict) -> None:
        item_type = item.get("type")

        if item_type == "agent_message":
            text = item.get("text")
            if text:
                self._print_section("Agent", str(text))
            return

        if item_type == "command_execution":
            item_id = str(item.get("id") or "")
            command = str(item.get("command") or "")

            if event_type == "item.started":
                self._print_command(item_id, command)
                return

            if event_type == "item.completed":
                if item_id not in self._printed_commands:
                    self._print_command(item_id, command)

                output = item.get("aggregated_output")
                if output:
                    self._blank_if_needed()
                    print(str(output), end="" if str(output).endswith("\n") else "\n")
                    self._need_blank = True

                exit_code = item.get("exit_code")
                if exit_code not in (None, 0):
                    self._blank_if_needed()
                    print(f"[exit {exit_code}]")
                    self._need_blank = True
                return

        text = item.get("text") or item.get("message")
        if text:
            self._print_section(str(item_type or "Item"), str(text))

    def _print_command(self, item_id: str, command: str) -> None:
        if item_id:
            self._printed_commands.add(item_id)
        if not command:
            return
        self._blank_if_needed()
        print(f"$ {self._display_command(command)}")
        self._need_blank = False

    def _display_command(self, command: str) -> str:
        try:
            parts = shlex.split(command)
        except ValueError:
            return command

        if len(parts) >= 3 and Path(parts[0]).name in {"bash", "sh"} and parts[1] == "-lc":
            return parts[2]
        return command

    def _print_section(self, label: str, text: str) -> None:
        self._blank_if_needed()
        print(f"{label}:")
        print(text, end="" if text.endswith("\n") else "\n")
        self._need_blank = True

    def _print_plain(self, text: str) -> None:
        self._blank_if_needed()
        print(text)
        self._need_blank = False

    def _blank_if_needed(self) -> None:
        if self._need_blank:
            print()
            self._need_blank = False


def iter_streams(paths: list[str]) -> Iterable[TextIO]:
    if not paths:
        yield sys.stdin
        return

    for path in paths:
        if path == "-":
            yield sys.stdin
        else:
            with open(path, encoding="utf-8", errors="replace") as f:
                yield f


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render Codex --json event logs as readable terminal output."
    )
    parser.add_argument("paths", nargs="*", help="Log file(s), or stdin when omitted")
    args = parser.parse_args()

    renderer = Renderer()
    try:
        for stream in iter_streams(args.paths):
            for line in stream:
                renderer.render_line(line)
                sys.stdout.flush()
    except BrokenPipeError:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
