"""CyberGym Playground — REST API server.

Task lifecycle:
  1. POST /tasks/request     → ASSIGNED (agent gets source_dir only)
  2. POST /tasks/{id}/identify → agent reports all findings
     → IDENTIFIED (fix revealed) or IDENTIFICATION_FAILED
  3. POST /tasks/{id}/submit   → agent submits PoC + harness
     → VERIFIED or EXPLOIT_FAILED
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from server.database import Database
from server.judge import judge_findings
from server.models import (
    HintTier,
    IdentifyRequest,
    IdentifyResponse,
    IdentifyResult,
    SubmitRequest,
    SubmitResponse,
    TaskDetail,
    TaskRequest,
    TaskResponse,
    TaskStatus,
    Verdict,
)
from server.registry import Registry
from server.scorer import Scorer
from server.workspace import WorkspaceManager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------
registry = Registry()
db: Database
workspace_mgr: WorkspaceManager
scorer: Scorer

DATA_DIR = Path(__file__).resolve().parent.parent
INSTANCES_DIR = DATA_DIR / "instances"
PROJECTS_FILE = DATA_DIR / "instances" / "projects.json"
RECIPES_DIR = DATA_DIR / "build_recipes"
COMMON_DIR = DATA_DIR / "common"
DB_PATH = DATA_DIR / "playground.db"

WORKSPACES_DIR = Path(os.environ.get(
    "PLAYGROUND_WORKSPACES", "/tmp/cyberplayground-workspaces"))
INTERNAL_DIR = Path(os.environ.get(
    "PLAYGROUND_INTERNAL", "/tmp/cyberplayground-internal"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db, workspace_mgr, scorer

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    logger.info("=" * 60)
    logger.info("CyberPlayground starting")
    logger.info("=" * 60)

    if PROJECTS_FILE.exists():
        registry.load_projects(PROJECTS_FILE)
    if INSTANCES_DIR.exists():
        registry.load_instances_dir(INSTANCES_DIR)
    logger.info("registry: %d instances across %d projects",
                registry.instance_count,
                len(registry.projects()))

    db = Database(DB_PATH)
    await db.connect()

    workspace_mgr = WorkspaceManager(
        WORKSPACES_DIR, internal_dir=INTERNAL_DIR)
    scorer = Scorer(RECIPES_DIR, COMMON_DIR if COMMON_DIR.exists() else None)

    logger.info("workspaces: %s", WORKSPACES_DIR)
    logger.info("internal:   %s", INTERNAL_DIR)
    logger.info("recipes:    %s (%d files)",
                RECIPES_DIR, len(list(RECIPES_DIR.glob("*.sh"))))
    logger.info("=" * 60)
    logger.info("ready — waiting for agents")
    logger.info("=" * 60)

    yield

    logger.info("shutting down")
    await db.close()


app = FastAPI(
    title="CyberPlayground",
    description="Vulnerability discovery evaluation platform for coding agents",
    version="0.2.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------

def _log(agent_id: str, level: str, msg: str, *args):
    """Log with [agent_id] prefix for easy filtering."""
    tagged = "[%s] " + msg
    getattr(logger, level)(tagged, agent_id, *args)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    t0 = time.monotonic()
    response = await call_next(request)
    dt = (time.monotonic() - t0) * 1000
    logger.info("%s %s → %d (%.0fms)",
                request.method, request.url.path,
                response.status_code, dt)
    return response


# ---------------------------------------------------------------------------
# Health / metadata
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "instances": registry.instance_count}


@app.get("/projects")
async def list_projects():
    return [p.model_dump() for p in registry.projects()]


@app.get("/instances")
async def list_instances(
    project: Optional[str] = Query(None),
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
):
    instances = registry.list_instances(project)
    total = len(instances)
    page = instances[offset: offset + limit]
    return {
        "total": total, "offset": offset, "limit": limit,
        "instances": [
            {"id": i.id, "project": i.project,
             "crash_type": i.crash_type, "family": i.family}
            for i in page
        ],
    }


# ---------------------------------------------------------------------------
# Stage 0: Task assignment
# ---------------------------------------------------------------------------

@app.post("/tasks/request", response_model=TaskResponse)
async def request_task(req: TaskRequest):
    a = req.agent_id
    _log(a, "info", "─" * 50)
    _log(a, "info", "TASK REQUEST project=%s tier=%s",
         req.project or "any", req.tier.value)

    already = await db.assigned_instance_ids(req.agent_id)
    if already:
        _log(a, "info", "  %d prior tasks, excluding those instances",
             len(already))

    instance = registry.pick_random(project=req.project, exclude=already)
    if not instance:
        _log(a, "warning", "  no available instances")
        raise HTTPException(404, "no available instances")

    _log(a, "info", "  selected instance=%s project=%s file=%s:%d",
         instance.id, instance.project,
         instance.diff.file, instance.diff.line)
    _log(a, "info", "  ground truth: '%s' → '%s'",
         instance.diff.before[:60], instance.diff.after[:60])

    try:
        t0 = time.monotonic()
        ws_id, vul_dir, fix_dir = await workspace_mgr.create_workspace(
            instance)
        dt = time.monotonic() - t0
        _log(a, "info", "  workspace created in %.1fs: %s", dt, ws_id)
    except Exception as e:
        _log(a, "error", "  workspace creation FAILED: %s", e)
        raise HTTPException(500, f"workspace creation failed: {e}")

    task_id = await db.create_task(
        instance_id=instance.id,
        project=instance.project,
        tier=req.tier,
        agent_id=req.agent_id,
        workspace_id=ws_id,
    )

    hint = registry.hint_for(instance.id, req.tier)
    now = datetime.now(timezone.utc)

    workspace_mgr.write_agent_instructions(
        workspace_id=ws_id,
        task_id=task_id,
        project=instance.project,
        hint=hint,
        build_recipe_url=f"/build_recipes/{instance.build_recipe}",
    )

    _log(a, "info", "  ✓ task=%s ASSIGNED", task_id)
    _log(a, "info", "  hint [%s]: %s", req.tier.value, hint[:80] + "...")
    _log(a, "info", "─" * 50)

    return TaskResponse(
        task_id=task_id,
        instance_id=instance.id,
        project=instance.project,
        tier=req.tier,
        hint=hint,
        repo_url=instance.repo_url,
        commit=instance.commit,
        build_recipe_url=f"/build_recipes/{instance.build_recipe}",
        workspace_id=ws_id,
        created_at=now,
    )


@app.get("/tasks/{task_id}", response_model=TaskDetail)
async def get_task(task_id: str):
    detail = await db.get_task(task_id)
    if not detail:
        raise HTTPException(404, "task not found")
    return detail


@app.get("/tasks/{task_id}/hint/{tier}")
async def get_hint(task_id: str, tier: HintTier):
    detail = await db.get_task(task_id)
    if not detail:
        raise HTTPException(404, "task not found")

    # enforce tier ceiling — agent can only access hints up to assigned tier
    tier_order = {"T0": 0, "T1": 1, "T3": 2}
    assigned = tier_order.get(detail.tier.value, 0)
    requested = tier_order.get(tier.value, 0)
    if requested > assigned:
        _log(detail.agent_id, "warning",
             "HINT DENIED task=%s requested=%s assigned=%s",
             task_id, tier.value, detail.tier.value)
        raise HTTPException(
            403,
            f"hint tier {tier.value} not available — "
            f"task was assigned at tier {detail.tier.value}")

    hint = registry.hint_for(detail.instance_id, tier)
    _log(detail.agent_id, "info", "HINT task=%s tier=%s: %s",
         task_id, tier.value, hint[:120])
    return {"task_id": task_id, "tier": tier.value, "hint": hint}


@app.get("/tasks/{task_id}/workspace")
async def get_workspace_info(task_id: str):
    detail = await db.get_task(task_id)
    if not detail:
        raise HTTPException(404, "task not found")
    ws = workspace_mgr.workspace_path(detail.workspace_id)
    if not ws:
        raise HTTPException(404, "workspace not found")

    resp = {
        "task_id": task_id,
        "workspace_id": detail.workspace_id,
        "source_dir": str(ws),
    }

    if detail.status in (TaskStatus.IDENTIFIED,
                         TaskStatus.VERIFIED,
                         TaskStatus.EXPLOIT_FAILED):
        fix = workspace_mgr.fix_dir(detail.workspace_id)
        if fix:
            resp["fix_source_dir"] = str(fix)

    return resp


# ---------------------------------------------------------------------------
# Stage 1: Bug identification
# ---------------------------------------------------------------------------

@app.post("/tasks/{task_id}/identify", response_model=IdentifyResponse)
async def identify_bugs(task_id: str, req: IdentifyRequest):
    detail = await db.get_task(task_id)
    if not detail:
        raise HTTPException(404, "task not found")
    if detail.status not in (TaskStatus.ASSIGNED,
                             TaskStatus.IDENTIFICATION_FAILED):
        raise HTTPException(
            400,
            f"task status is {detail.status.value}; "
            f"identify only allowed in ASSIGNED or IDENTIFICATION_FAILED")

    if not req.findings:
        raise HTTPException(400, "at least one finding required")

    instance = registry.get(detail.instance_id)
    if not instance:
        raise HTTPException(500, "instance not found")

    logger.info("═" * 50)
    a = detail.agent_id
    _log(a, "info", "IDENTIFY task=%s instance=%s",
         task_id, detail.instance_id)
    _log(a, "info", "  reported %d findings:", len(req.findings))
    for i, f in enumerate(req.findings):
        _log(a, "info", "    [%d] %s:%s — %s",
             i, f.file, f.line or "?",
             f.description[:80])
    _log(a, "info", "  ground truth: %s:%d (%s)",
         instance.diff.file, instance.diff.line,
         instance.crash_type)

    t0 = time.monotonic()
    judgements = await judge_findings(instance, req.findings)
    judge_dt = time.monotonic() - t0

    matched_index = None
    best_result = IdentifyResult.NO_MATCH
    for j in judgements:
        if j.result == IdentifyResult.MATCH:
            matched_index = j.finding_index
            best_result = IdentifyResult.MATCH
            break
        if j.result == IdentifyResult.PARTIAL and best_result != IdentifyResult.MATCH:
            best_result = IdentifyResult.PARTIAL

    _log(a, "info", "  judge completed in %.1fs:", judge_dt)
    for j in judgements:
        icon = {"match": "✓", "partial": "~", "no_match": "✗"}[j.result.value]
        _log(a, "info", "    [%d] %s %s (conf=%.1f) — %s",
             j.finding_index, icon, j.result.value,
             j.confidence, j.explanation[:80])

    if best_result == IdentifyResult.MATCH:
        _log(a, "info", "  ✓ IDENTIFIED — finding #%d matched!", matched_index)
    else:
        _log(a, "info", "  ✗ IDENTIFICATION FAILED — no findings matched")
    logger.info("═" * 50)

    await db.identify_task(
        task_id=task_id,
        result=best_result,
        num_findings=len(req.findings),
        matched_finding_index=matched_index,
        findings_json=json.dumps(
            [f.model_dump() for f in req.findings]),
        judgements_json=json.dumps(
            [j.model_dump() for j in judgements]),
    )

    resp = IdentifyResponse(
        task_id=task_id,
        status=(TaskStatus.IDENTIFIED if best_result == IdentifyResult.MATCH
                else TaskStatus.IDENTIFICATION_FAILED),
        total_findings=len(req.findings),
        matched_finding=matched_index,
        judgements=judgements,
    )

    if best_result == IdentifyResult.MATCH:
        fix = workspace_mgr.fix_dir(detail.workspace_id)
        if fix:
            resp.fix_source_dir = str(fix)

    return resp


# ---------------------------------------------------------------------------
# Stage 2: PoC submission (only after identification)
# ---------------------------------------------------------------------------

@app.post("/tasks/{task_id}/submit", response_model=SubmitResponse)
async def submit_task(task_id: str, req: SubmitRequest):
    detail = await db.get_task(task_id)
    if not detail:
        raise HTTPException(404, "task not found")
    if detail.status not in (TaskStatus.IDENTIFIED,
                             TaskStatus.EXPLOIT_FAILED):
        raise HTTPException(
            400,
            f"task status is {detail.status.value}; "
            f"submit requires IDENTIFIED status (call /identify first)")

    instance = registry.get(detail.instance_id)
    if not instance:
        raise HTTPException(500, "instance not found")

    logger.info("▶" * 25)
    a = detail.agent_id
    _log(a, "info", "SUBMIT task=%s instance=%s",
         task_id, detail.instance_id)
    _log(a, "info", "  poc size: %d bytes (b64)",
         len(req.poc) if req.poc else 0)
    _log(a, "info", "  harness size: %d bytes (b64)",
         len(req.harness) if req.harness else 0)
    if req.bug_file:
        _log(a, "info", "  agent's bug location: %s:%s",
             req.bug_file, req.bug_line or "?")

    vul_dir = workspace_mgr.vul_dir(detail.workspace_id)
    fix_dir = workspace_mgr.fix_dir(detail.workspace_id)
    if not vul_dir or not fix_dir:
        _log(a, "error", "  workspace dirs not found!")
        raise HTTPException(500, "workspace dirs not found")

    _log(a, "info", "  building vul binary...")
    t0 = time.monotonic()
    result = await scorer.verify_poc(
        instance, vul_dir, fix_dir, req.poc, req.harness)
    verify_dt = time.monotonic() - t0
    result.task_id = task_id

    partial = scorer.compute_partial_credit(
        instance,
        bug_file=req.bug_file,
        bug_function=req.bug_function,
        bug_line=req.bug_line,
    )
    result.partial_credit = partial

    if result.verdict == Verdict.PASS:
        _log(a, "info", "  ✓ VERIFIED in %.1fs — vul crashed, fix clean", verify_dt)
    elif result.verdict == Verdict.BUILD_ERROR:
        _log(a, "info", "  ✗ BUILD_ERROR in %.1fs", verify_dt)
        _log(a, "info", "    %s", result.crash_output[:200])
    elif result.verdict == Verdict.TIMEOUT:
        _log(a, "info", "  ✗ TIMEOUT in %.1fs", verify_dt)
    else:
        _log(a, "info", "  ✗ EXPLOIT FAILED in %.1fs", verify_dt)
        _log(a, "info", "    vul: %s", result.crash_output[:120])
        _log(a, "info", "    fix: %s", result.fix_output[:120])

    if partial:
        _log(a, "info", "  partial credit: %s", partial)
    logger.info("▶" * 25)

    await db.submit_task(
        task_id=task_id,
        verdict=result.verdict,
        crash_output=result.crash_output,
        fix_output=result.fix_output,
        partial_credit=partial,
        elapsed_seconds=result.elapsed_seconds,
        poc_b64=req.poc,
        harness_b64=req.harness,
        bug_file=req.bug_file,
        bug_function=req.bug_function,
        bug_line=req.bug_line,
        bug_description=req.bug_description,
    )

    return result


# ---------------------------------------------------------------------------
# Post-eval
# ---------------------------------------------------------------------------

@app.get("/tasks/{task_id}/ground_truth")
async def ground_truth(task_id: str):
    detail = await db.get_task(task_id)
    if not detail:
        raise HTTPException(404, "task not found")
    if detail.status in (TaskStatus.ASSIGNED,):
        raise HTTPException(
            400, "identify bugs before viewing ground truth")
    instance = registry.get(detail.instance_id)
    if not instance:
        raise HTTPException(500, "instance not found")
    _log(detail.agent_id, "info", "GROUND TRUTH revealed for task=%s",
         task_id)
    return {
        "task_id": task_id,
        "instance_id": instance.id,
        "diff": instance.diff.model_dump(),
        "crash_type": instance.crash_type,
        "family": instance.family,
    }


@app.get("/scoreboard")
async def scoreboard():
    sb = await db.scoreboard()
    sb.total_instances = registry.instance_count
    return sb


@app.get("/build_recipes/{name}")
async def get_build_recipe(name: str):
    recipe = RECIPES_DIR / f"{name}.sh"
    if not recipe.exists():
        raise HTTPException(404, f"recipe {name} not found")
    logger.info("BUILD RECIPE served: %s", name)
    return FileResponse(recipe, media_type="text/x-shellscript")


@app.get("/tasks")
async def list_tasks(
    agent_id: Optional[str] = Query(None),
    project: Optional[str] = Query(None),
    status: Optional[TaskStatus] = Query(None),
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
):
    tasks = await db.list_tasks(agent_id, project, status, limit, offset)
    return {"tasks": [t.model_dump() for t in tasks]}


# ---------------------------------------------------------------------------
# Batch evaluation
# ---------------------------------------------------------------------------

class EvalStartRequest(BaseModel):
    agent_id: str
    project: Optional[str] = None
    tier: HintTier = HintTier.T0
    instance_ids: Optional[list[str]] = None


class EvalStartResponse(BaseModel):
    eval_id: str
    agent_id: str
    total: int


@app.post("/eval/start", response_model=EvalStartResponse)
async def start_eval(req: EvalStartRequest):
    """Pre-create task records (no workspaces yet) for all instances."""
    if req.instance_ids:
        instances = [registry.get(iid) for iid in req.instance_ids]
        instances = [i for i in instances if i is not None]
    else:
        instances = registry.list_instances(req.project)

    if not instances:
        raise HTTPException(404, "no instances found")

    eval_id = f"eval_{req.agent_id}_{uuid.uuid4().hex[:8]}"
    count = 0

    logger.info("=" * 60)
    logger.info("EVAL START eval=%s agent=%s instances=%d tier=%s",
                eval_id, req.agent_id, len(instances), req.tier.value)

    for inst in instances:
        # create task record with empty workspace — created on /next
        task_id = await db.create_task(
            instance_id=inst.id,
            project=inst.project,
            tier=req.tier,
            agent_id=req.agent_id,
            workspace_id="",
        )
        count += 1
        logger.info("  queued task=%s instance=%s", task_id, inst.id)

    logger.info("EVAL START complete: %d tasks queued", count)
    logger.info("=" * 60)

    return EvalStartResponse(
        eval_id=eval_id,
        agent_id=req.agent_id,
        total=count,
    )


@app.get("/eval/{agent_id}/next")
async def eval_next(agent_id: str):
    """Get the next task for this agent.

    - Creates workspace on demand for the next unstarted task
    - Deletes the previous task's workspace to prevent cross-task diffing
    - Returns one task only
    """
    all_tasks = await db.list_tasks(agent_id=agent_id, limit=9999)

    # find completed tasks with workspaces still alive — clean them up
    for t in all_tasks:
        if t.workspace_id and t.status in (
            TaskStatus.VERIFIED, TaskStatus.EXPLOIT_FAILED,
            TaskStatus.IDENTIFICATION_FAILED,
        ):
            await workspace_mgr.cleanup_workspace(t.workspace_id)
            await db.clear_workspace(t.task_id)

    # find next unstarted task — try each until workspace creation succeeds
    candidates = [t for t in all_tasks
                  if t.status == TaskStatus.ASSIGNED and not t.workspace_id]

    if not candidates:
        # check if there are any still in-progress
        active = [t for t in all_tasks if t.status == TaskStatus.ASSIGNED
                  and t.workspace_id]
        if active:
            t = active[0]
            ws = workspace_mgr.workspace_path(t.workspace_id)
            hint = registry.hint_for(t.instance_id, t.tier)
            return {
                "task_id": t.task_id,
                "instance_id": t.instance_id,
                "project": t.project,
                "hint": hint,
                "source_dir": str(ws) if ws else "",
                "remaining": sum(1 for x in all_tasks
                                 if x.status == TaskStatus.ASSIGNED) - 1,
            }
        return {"task_id": None, "remaining": 0, "message": "all tasks completed"}

    # try candidates in order, skip ones that fail workspace creation
    for next_task in candidates:
        instance = registry.get(next_task.instance_id)
        if not instance:
            _log(agent_id, "warning", "  skipping %s: instance not in registry",
                 next_task.instance_id)
            await db.mark_task_skipped(next_task.task_id)
            continue

        try:
            ws_id, vul_dir, fix_dir = await workspace_mgr.create_workspace(
                instance)
        except Exception as e:
            _log(agent_id, "warning", "  skipping %s: workspace failed: %s",
                 instance.id, e)
            await db.mark_task_skipped(next_task.task_id)
            continue

        # success — set up this task
        await db.set_workspace(next_task.task_id, ws_id)

        hint = registry.hint_for(instance.id, next_task.tier)

        workspace_mgr.write_agent_instructions(
            workspace_id=ws_id,
            task_id=next_task.task_id,
            project=instance.project,
            hint=hint,
            build_recipe_url=f"/build_recipes/{instance.build_recipe}",
        )

        remaining = sum(1 for t in all_tasks
                        if t.status == TaskStatus.ASSIGNED) - 1

        _log(agent_id, "info", "─" * 50)
        _log(agent_id, "info", "NEXT TASK task=%s instance=%s (%d remaining)",
             next_task.task_id, instance.id, remaining)
        _log(agent_id, "info", "─" * 50)

        return {
            "task_id": next_task.task_id,
            "instance_id": next_task.instance_id,
            "project": next_task.project,
            "hint": hint,
            "source_dir": str(vul_dir),
            "build_recipe_url": f"/build_recipes/{instance.build_recipe}",
            "remaining": remaining,
        }

    # all candidates failed
    return {"task_id": None, "remaining": 0,
            "message": "all remaining tasks failed workspace creation"}


@app.delete("/eval/{agent_id}/reset")
async def eval_reset(agent_id: str):
    """Delete all tasks for an agent so you can start fresh."""
    # clean up any remaining workspaces
    all_tasks = await db.list_tasks(agent_id=agent_id, limit=9999)
    cleaned = 0
    for t in all_tasks:
        if t.workspace_id:
            await workspace_mgr.cleanup_workspace(t.workspace_id)
            cleaned += 1
    count = await db.delete_agent_tasks(agent_id)
    logger.info("RESET agent=%s: deleted %d tasks, cleaned %d workspaces",
                agent_id, count, cleaned)
    return {"agent_id": agent_id, "deleted": count, "workspaces_cleaned": cleaned}


@app.get("/eval/{agent_id}/pending")
async def eval_pending(agent_id: str):
    """How many tasks remain — no workspace paths exposed."""
    all_tasks = await db.list_tasks(agent_id=agent_id, limit=9999)
    pending = sum(1 for t in all_tasks if t.status == TaskStatus.ASSIGNED)
    skipped = sum(1 for t in all_tasks if t.status == TaskStatus.SKIPPED)
    completed = sum(1 for t in all_tasks if t.status in (
        TaskStatus.VERIFIED, TaskStatus.EXPLOIT_FAILED,
        TaskStatus.IDENTIFIED, TaskStatus.IDENTIFICATION_FAILED))
    return {
        "agent_id": agent_id,
        "total": len(all_tasks),
        "pending": pending,
        "skipped": skipped,
        "completed": completed,
    }


@app.get("/eval/{agent_id}/report")
async def eval_report(agent_id: str):
    """Final evaluation report for an agent."""
    tasks = await db.list_tasks(agent_id=agent_id, limit=9999)
    if not tasks:
        raise HTTPException(404, f"no tasks found for agent {agent_id}")

    total = len(tasks)
    by_status = {}
    by_project = {}
    by_instance = []

    for t in tasks:
        st = t.status.value
        by_status[st] = by_status.get(st, 0) + 1

        proj = t.project
        if proj not in by_project:
            by_project[proj] = {
                "total": 0, "assigned": 0,
                "identified": 0, "identification_failed": 0,
                "verified": 0, "exploit_failed": 0,
            }
        by_project[proj]["total"] += 1
        if st in by_project[proj]:
            by_project[proj][st] += 1

        by_instance.append({
            "task_id": t.task_id,
            "instance_id": t.instance_id,
            "project": t.project,
            "status": st,
            "identification_result": (
                t.identification_result.value
                if t.identification_result else None),
            "num_findings": t.num_findings,
            "verdict": t.verdict.value if t.verdict else None,
            "elapsed_seconds": t.elapsed_seconds,
        })

    completed = total - by_status.get("assigned", 0)
    identified = (by_status.get("identified", 0)
                  + by_status.get("verified", 0)
                  + by_status.get("exploit_failed", 0))
    verified = by_status.get("verified", 0)

    report = {
        "agent_id": agent_id,
        "total_tasks": total,
        "completed": completed,
        "pending": by_status.get("assigned", 0),
        "identification_rate": identified / completed if completed else 0,
        "exploit_rate": verified / identified if identified else 0,
        "overall_pass_rate": verified / total if total else 0,
        "by_status": by_status,
        "by_project": by_project,
        "instances": by_instance,
    }

    logger.info("EVAL REPORT for agent=%s: %d tasks, %d identified, %d verified (%.0f%%)",
                agent_id, total, identified, verified,
                (verified / total * 100) if total else 0)

    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cli():
    parser = argparse.ArgumentParser(
        description="CyberGym Playground server")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    uvicorn.run("server.main:app", host=args.host, port=args.port,
                reload=args.reload)


if __name__ == "__main__":
    cli()
