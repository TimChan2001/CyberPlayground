"""Instance registry — loads and indexes all benchmark instances from JSON manifests."""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Optional

from server.models import HintData, HintTier, InjectionDiff, Instance, ProjectInfo

logger = logging.getLogger(__name__)


def _generate_hints(inst_data: dict, project: str) -> HintData:
    """Derive hint strings from instance metadata."""
    crash = inst_data.get("crash_type", "memory safety bug")
    diff = inst_data.get("diff", inst_data)
    file = diff.get("file", "")
    line = diff.get("line", 0)
    explanation = inst_data.get("explanation", "")

    # T0: blind
    t0 = (
        f"This {project} build contains a memory safety vulnerability. "
        f"Identify the vulnerable code with /identify."
    )

    # T1: area hint — subsystem derived from file path
    parts = Path(file).stem.split("_")
    subsystem = parts[0] if parts else file
    t1 = (
        f"This {project} build has a {crash} vulnerability. "
        f"The bug is in the '{subsystem}' subsystem (source files matching *{subsystem}*). "
        f"Identify the matching candidate with /identify."
    )

    # T2: function-level hint
    t2 = (
        f"This {project} build has a {crash} vulnerability in {file} near line {line}. "
    )
    if explanation:
        t2 += f"{explanation} "
    t2 += "Identify this candidate with /identify."

    return HintData(T0=t0, T1=t1, T2=t2)


class Registry:
    """In-memory index of all available instances."""

    def __init__(self) -> None:
        self._instances: dict[str, Instance] = {}
        self._projects: dict[str, ProjectInfo] = {}
        self._by_project: dict[str, list[str]] = {}

    # -- loading -----------------------------------------------------------

    def load_projects(self, path: Path) -> None:
        """Load projects.json — maps project name to repo URL, commit, etc."""
        data = json.loads(path.read_text())
        for name, info in data.items():
            self._projects[name] = ProjectInfo(name=name, **info)
        logger.info("loaded %d projects from %s", len(self._projects), path)

    def load_instances_dir(self, dir_path: Path) -> None:
        """Load all instance JSON files from a directory."""
        for p in sorted(dir_path.glob("*.json")):
            if p.name == "projects.json" or p.name.startswith("._"):
                continue
            try:
                self._load_instance_file(p)
            except Exception:
                logger.warning("skipping bad instance file %s", p, exc_info=True)
        logger.info("registry: %d instances across %d projects",
                     len(self._instances), len(self._by_project))

    def _load_instance_file(self, path: Path) -> None:
        data = json.loads(path.read_text())
        items = data if isinstance(data, list) else [data]
        for item in items:
            if not isinstance(item, dict) or "id" not in item or "project" not in item:
                logger.debug("skipping non-instance item in %s", path)
                continue
            diff_data = item.get("diff", item)
            if not all(k in diff_data for k in ("file", "line", "before", "after")):
                logger.debug(
                    "skipping unsupported instance item in %s: %s",
                    path, item.get("id", "(unknown)"))
                continue
            self._register(item)

    def _register(self, data: dict) -> None:
        inst_id = data["id"]
        project = data["project"]
        proj_info = self._projects.get(project)
        if not proj_info:
            logger.warning("instance %s references unknown project %s", inst_id, project)
            return

        hints = _generate_hints(data, project)

        diff_data = data.get("diff", data)
        inst = Instance(
            id=inst_id,
            project=project,
            repo_url=proj_info.repo_url,
            commit=proj_info.commit,
            diff=InjectionDiff(
                file=diff_data["file"],
                line=diff_data["line"],
                before=diff_data["before"],
                after=diff_data["after"],
            ),
            crash_type=data.get("crash_type", diff_data.get("crash_type", "")),
            family=data.get("family", ""),
            build_recipe=proj_info.build_recipe,
            hints=hints,
        )
        self._instances[inst_id] = inst
        self._by_project.setdefault(project, []).append(inst_id)

    # -- queries -----------------------------------------------------------

    def get(self, instance_id: str) -> Optional[Instance]:
        return self._instances.get(instance_id)

    def get_project(self, name: str) -> Optional[ProjectInfo]:
        return self._projects.get(name)

    def list_instances(self, project: Optional[str] = None) -> list[Instance]:
        if project:
            ids = self._by_project.get(project, [])
            return [self._instances[i] for i in ids]
        return list(self._instances.values())

    def pick_random(self, project: Optional[str] = None,
                    exclude: Optional[set[str]] = None) -> Optional[Instance]:
        candidates = self.list_instances(project)
        if exclude:
            candidates = [c for c in candidates if c.id not in exclude]
        return random.choice(candidates) if candidates else None

    def projects(self) -> list[ProjectInfo]:
        return list(self._projects.values())

    @property
    def instance_count(self) -> int:
        return len(self._instances)

    def hint_for(self, instance_id: str, tier: HintTier) -> str:
        inst = self._instances.get(instance_id)
        if not inst:
            return ""
        return getattr(inst.hints, tier.value, "")
