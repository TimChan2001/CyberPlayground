#!/usr/bin/env python3
"""Sample CyberPlayground instance ids deterministically."""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INSTANCES_DIR = REPO_ROOT / "instances"


def warn(message: str) -> None:
    print(f"warning: {message}", file=sys.stderr)


def load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        warn(f"skipping {path}: not UTF-8 ({exc})")
    except json.JSONDecodeError as exc:
        warn(f"skipping {path}: invalid JSON ({exc})")
    return None


def candidate_items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]

    if not isinstance(data, dict):
        return []

    if isinstance(data.get("id"), str) and isinstance(data.get("project"), str):
        return [data]

    nested = data.get("instances")
    if isinstance(nested, list):
        return [item for item in nested if isinstance(item, dict)]

    return []


def iter_instance_files(instances_dir: Path):
    for path in sorted(instances_dir.glob("*.json")):
        if path.name.startswith("._") or path.name.startswith("."):
            continue
        if path.name == "projects.json":
            continue
        yield path


def load_instances(instances_dir: Path) -> list[dict[str, str]]:
    seen: set[str] = set()
    instances: list[dict[str, str]] = []

    for path in iter_instance_files(instances_dir):
        data = load_json(path)
        if data is None:
            continue

        for item in candidate_items(data):
            inst_id = item.get("id")
            project = item.get("project")
            if not isinstance(inst_id, str) or not isinstance(project, str):
                continue
            if inst_id in seen:
                warn(f"duplicate instance id {inst_id!r} in {path}; keeping first")
                continue
            seen.add(inst_id)
            instances.append({
                "id": inst_id,
                "project": project,
                "source_file": str(path),
            })

    instances.sort(key=lambda item: (item["project"], item["id"]))
    return instances


def write_output(text: str, out: Path | None) -> None:
    if out is None:
        print(text, end="" if text.endswith("\n") else "\n")
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sample CyberPlayground instance ids deterministically."
    )
    parser.add_argument(
        "-n", "--count",
        type=int,
        default=100,
        help="Number of instance ids to sample. Default: 100.",
    )
    parser.add_argument(
        "--seed",
        default="0",
        help="Deterministic random seed. Default: 0.",
    )
    parser.add_argument(
        "--instances-dir",
        type=Path,
        default=DEFAULT_INSTANCES_DIR,
        help=f"Instance manifest directory. Default: {DEFAULT_INSTANCES_DIR}",
    )
    parser.add_argument(
        "--project",
        action="append",
        default=[],
        help="Restrict to a project. May be repeated.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write output to this file instead of stdout.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output a JSON array instead of one id per line.",
    )
    parser.add_argument(
        "--with-project",
        action="store_true",
        help="Output '<id><tab><project>' lines. Ignored with --json.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.count < 1:
        print("--count must be at least 1", file=sys.stderr)
        return 2

    instances = load_instances(args.instances_dir)
    if args.project:
        wanted = set(args.project)
        instances = [item for item in instances if item["project"] in wanted]

    if args.count > len(instances):
        print(
            f"requested {args.count} instances, but only {len(instances)} match",
            file=sys.stderr,
        )
        return 2

    rng = random.Random(args.seed)
    sampled = rng.sample(instances, args.count)

    if args.json:
        output = json.dumps([item["id"] for item in sampled], indent=2) + "\n"
    elif args.with_project:
        output = "".join(f"{item['id']}\t{item['project']}\n" for item in sampled)
    else:
        output = "".join(f"{item['id']}\n" for item in sampled)

    write_output(output, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
