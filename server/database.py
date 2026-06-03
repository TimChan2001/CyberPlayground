"""SQLite-backed storage for tasks and evaluation results."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiosqlite

from server.models import (
    AgentScore,
    HintTier,
    IdentifyResult,
    ScoreboardResponse,
    TaskDetail,
    TaskStatus,
    Verdict,
)

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    task_id               TEXT PRIMARY KEY,
    instance_id           TEXT NOT NULL,
    project               TEXT NOT NULL,
    tier                  TEXT NOT NULL,
    agent_id              TEXT NOT NULL DEFAULT 'default',
    status                TEXT NOT NULL DEFAULT 'assigned',
    workspace_id          TEXT NOT NULL DEFAULT '',
    created_at            TEXT NOT NULL,

    -- identification stage
    identified_at         TEXT,
    identification_result TEXT,
    num_findings          INTEGER DEFAULT 0,
    matched_finding_index INTEGER,
    findings_json         TEXT DEFAULT '[]',
    judgements_json       TEXT DEFAULT '[]',

    -- exploit stage
    submitted_at          TEXT,
    verdict               TEXT,
    crash_output          TEXT DEFAULT '',
    fix_output            TEXT DEFAULT '',
    partial_credit        TEXT DEFAULT '{}',
    elapsed_seconds       REAL DEFAULT 0.0,
    poc_b64               TEXT,
    harness_b64           TEXT,
    bug_file              TEXT,
    bug_function          TEXT,
    bug_line              INTEGER,
    bug_description       TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_agent ON tasks(agent_id);
CREATE INDEX IF NOT EXISTS idx_tasks_instance ON tasks(instance_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project);
"""


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(SCHEMA)
        await self._db.commit()
        logger.info("database ready at %s", self.db_path)

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    # -- task CRUD ---------------------------------------------------------

    async def create_task(
        self,
        instance_id: str,
        project: str,
        tier: HintTier,
        agent_id: str,
        workspace_id: str,
    ) -> str:
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            """INSERT INTO tasks
               (task_id, instance_id, project, tier, agent_id, workspace_id,
                status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (task_id, instance_id, project, tier.value, agent_id, workspace_id,
             TaskStatus.ASSIGNED.value, now),
        )
        await self._db.commit()
        return task_id

    async def get_task(self, task_id: str) -> Optional[TaskDetail]:
        async with self._db.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        return self._row_to_detail(row)

    async def identify_task(
        self,
        task_id: str,
        result: IdentifyResult,
        num_findings: int,
        matched_finding_index: Optional[int],
        findings_json: str,
        judgements_json: str,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if result == IdentifyResult.MATCH:
            status = TaskStatus.IDENTIFIED
        else:
            status = TaskStatus.IDENTIFICATION_FAILED
        await self._db.execute(
            """UPDATE tasks SET
               status = ?, identified_at = ?,
               identification_result = ?, num_findings = ?,
               matched_finding_index = ?,
               findings_json = ?, judgements_json = ?
               WHERE task_id = ?""",
            (status.value, now, result.value, num_findings,
             matched_finding_index, findings_json, judgements_json,
             task_id),
        )
        await self._db.commit()

    async def submit_task(
        self,
        task_id: str,
        verdict: Verdict,
        crash_output: str = "",
        fix_output: str = "",
        partial_credit: Optional[dict] = None,
        elapsed_seconds: float = 0.0,
        poc_b64: str = "",
        harness_b64: str = "",
        bug_file: Optional[str] = None,
        bug_function: Optional[str] = None,
        bug_line: Optional[int] = None,
        bug_description: Optional[str] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        status = (TaskStatus.VERIFIED if verdict == Verdict.PASS
                  else TaskStatus.EXPLOIT_FAILED)
        await self._db.execute(
            """UPDATE tasks SET
               status = ?, submitted_at = ?, verdict = ?,
               crash_output = ?, fix_output = ?,
               partial_credit = ?, elapsed_seconds = ?,
               poc_b64 = ?, harness_b64 = ?, bug_file = ?, bug_function = ?,
               bug_line = ?, bug_description = ?
               WHERE task_id = ?""",
            (status.value, now, verdict.value,
             crash_output, fix_output,
             json.dumps(partial_credit or {}), elapsed_seconds,
             poc_b64, harness_b64, bug_file, bug_function, bug_line, bug_description,
             task_id),
        )
        await self._db.commit()

    async def set_workspace(self, task_id: str, workspace_id: str) -> None:
        await self._db.execute(
            "UPDATE tasks SET workspace_id = ? WHERE task_id = ?",
            (workspace_id, task_id),
        )
        await self._db.commit()

    async def clear_workspace(self, task_id: str) -> None:
        await self._db.execute(
            "UPDATE tasks SET workspace_id = '' WHERE task_id = ?",
            (task_id,),
        )
        await self._db.commit()

    async def mark_task_skipped(self, task_id: str) -> None:
        await self._db.execute(
            "UPDATE tasks SET status = ? WHERE task_id = ?",
            (TaskStatus.SKIPPED.value, task_id),
        )
        await self._db.commit()

    async def delete_agent_tasks(self, agent_id: str) -> int:
        async with self._db.execute(
            "SELECT COUNT(*) as c FROM tasks WHERE agent_id = ?",
            (agent_id,),
        ) as cur:
            count = (await cur.fetchone())["c"]
        await self._db.execute(
            "DELETE FROM tasks WHERE agent_id = ?", (agent_id,))
        await self._db.commit()
        return count

    async def list_tasks(
        self,
        agent_id: Optional[str] = None,
        project: Optional[str] = None,
        status: Optional[TaskStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TaskDetail]:
        clauses, params = [], []
        if agent_id:
            clauses.append("agent_id = ?")
            params.append(agent_id)
        if project:
            clauses.append("project = ?")
            params.append(project)
        if status:
            clauses.append("status = ?")
            params.append(status.value)
        where = " AND ".join(clauses) if clauses else "1=1"
        params.extend([limit, offset])
        async with self._db.execute(
            f"SELECT * FROM tasks WHERE {where} "
            f"ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        ) as cur:
            rows = await cur.fetchall()
        return [self._row_to_detail(r) for r in rows]

    async def assigned_instance_ids(self, agent_id: Optional[str] = None) -> set[str]:
        q = "SELECT DISTINCT instance_id FROM tasks"
        params = []
        if agent_id:
            q += " WHERE agent_id = ?"
            params.append(agent_id)
        async with self._db.execute(q, params) as cur:
            rows = await cur.fetchall()
        return {r["instance_id"] for r in rows}

    # -- scoreboard --------------------------------------------------------

    async def scoreboard(self) -> ScoreboardResponse:
        agents: dict[str, AgentScore] = {}

        async with self._db.execute(
            """SELECT agent_id, project, tier, status,
                      identification_result, num_findings,
                      verdict, elapsed_seconds
               FROM tasks"""
        ) as cur:
            rows = await cur.fetchall()

        for row in rows:
            aid = row["agent_id"]
            if aid not in agents:
                agents[aid] = AgentScore(agent_id=aid)
            a = agents[aid]
            a.total_tasks += 1

            st = row["status"]
            if st == TaskStatus.IDENTIFIED.value:
                a.identified += 1
            elif st == TaskStatus.IDENTIFICATION_FAILED.value:
                a.identification_failed += 1
            elif st == TaskStatus.VERIFIED.value:
                a.identified += 1
                a.verified += 1
            elif st == TaskStatus.EXPLOIT_FAILED.value:
                a.identified += 1
                a.exploit_failed += 1

            proj = row["project"]
            a.by_project.setdefault(proj, {
                "total": 0, "identified": 0, "verified": 0})
            a.by_project[proj]["total"] += 1
            if st in (TaskStatus.IDENTIFIED.value,
                      TaskStatus.VERIFIED.value,
                      TaskStatus.EXPLOIT_FAILED.value):
                a.by_project[proj]["identified"] += 1
            if st == TaskStatus.VERIFIED.value:
                a.by_project[proj]["verified"] += 1

            tier = row["tier"]
            a.by_tier.setdefault(tier, {
                "total": 0, "identified": 0, "verified": 0})
            a.by_tier[tier]["total"] += 1
            if st in (TaskStatus.IDENTIFIED.value,
                      TaskStatus.VERIFIED.value,
                      TaskStatus.EXPLOIT_FAILED.value):
                a.by_tier[tier]["identified"] += 1
            if st == TaskStatus.VERIFIED.value:
                a.by_tier[tier]["verified"] += 1

        for a in agents.values():
            completed = (a.identified + a.identification_failed)
            a.identification_rate = (
                a.identified / completed if completed else 0.0)
            exploit_attempted = a.verified + a.exploit_failed
            a.exploit_rate = (
                a.verified / exploit_attempted if exploit_attempted else 0.0)

        # avg findings
        async with self._db.execute(
            """SELECT agent_id, AVG(num_findings) as avg_f
               FROM tasks WHERE num_findings > 0 GROUP BY agent_id"""
        ) as cur:
            for row in await cur.fetchall():
                if row["agent_id"] in agents:
                    agents[row["agent_id"]].avg_findings_per_task = (
                        row["avg_f"] or 0.0)

        # avg elapsed
        async with self._db.execute(
            """SELECT agent_id, AVG(elapsed_seconds) as avg_e
               FROM tasks WHERE elapsed_seconds > 0 GROUP BY agent_id"""
        ) as cur:
            for row in await cur.fetchall():
                if row["agent_id"] in agents:
                    agents[row["agent_id"]].avg_elapsed_seconds = (
                        row["avg_e"] or 0.0)

        async with self._db.execute(
            "SELECT COUNT(*) as c FROM tasks"
        ) as cur:
            total_tasks = (await cur.fetchone())["c"]

        return ScoreboardResponse(
            agents=list(agents.values()),
            total_tasks=total_tasks,
        )

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _row_to_detail(row) -> TaskDetail:
        ident_result = None
        if row["identification_result"]:
            try:
                ident_result = IdentifyResult(row["identification_result"])
            except ValueError:
                pass

        return TaskDetail(
            task_id=row["task_id"],
            instance_id=row["instance_id"],
            project=row["project"],
            tier=HintTier(row["tier"]),
            status=TaskStatus(row["status"]),
            agent_id=row["agent_id"],
            workspace_id=row["workspace_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            identified_at=(
                datetime.fromisoformat(row["identified_at"])
                if row["identified_at"] else None
            ),
            submitted_at=(
                datetime.fromisoformat(row["submitted_at"])
                if row["submitted_at"] else None
            ),
            identification_result=ident_result,
            num_findings=row["num_findings"] or 0,
            matched_finding_index=row["matched_finding_index"],
            verdict=Verdict(row["verdict"]) if row["verdict"] else None,
            partial_credit=json.loads(row["partial_credit"] or "{}"),
            elapsed_seconds=row["elapsed_seconds"] or 0.0,
        )
