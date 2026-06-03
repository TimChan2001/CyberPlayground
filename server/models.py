"""Data models for cyberplayground.

Task lifecycle:
  ASSIGNED → (agent reports findings) → IDENTIFIED / IDENTIFICATION_FAILED
  IDENTIFIED → (agent submits PoC+harness) → VERIFIED / EXPLOIT_FAILED
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class HintTier(str, enum.Enum):
    T0 = "T0"
    T1 = "T1"
    T3 = "T3"


class TaskStatus(str, enum.Enum):
    ASSIGNED = "assigned"
    SKIPPED = "skipped"
    IDENTIFIED = "identified"
    IDENTIFICATION_FAILED = "identification_failed"
    VERIFIED = "verified"
    EXPLOIT_FAILED = "exploit_failed"


class Verdict(str, enum.Enum):
    PASS = "pass"
    FAIL = "fail"
    BUILD_ERROR = "build_error"
    TIMEOUT = "timeout"


class IdentifyResult(str, enum.Enum):
    MATCH = "match"
    PARTIAL = "partial"
    NO_MATCH = "no_match"


# ---------------------------------------------------------------------------
# Instance — a single injected bug (immutable, loaded from JSON manifests)
# ---------------------------------------------------------------------------

class InjectionDiff(BaseModel):
    file: str
    line: int
    before: str
    after: str


class HintData(BaseModel):
    T0: str = ""
    T1: str = ""
    T3: str = ""


class Instance(BaseModel):
    id: str
    project: str
    repo_url: str
    commit: str
    diff: InjectionDiff
    crash_type: str = ""
    family: str = ""
    build_recipe: str = ""
    hints: HintData = Field(default_factory=HintData)


class ProjectInfo(BaseModel):
    name: str
    repo_url: str
    commit: str
    build_recipe: str
    description: str = ""


# ---------------------------------------------------------------------------
# Bug finding — agent reports what it found
# ---------------------------------------------------------------------------

class BugFinding(BaseModel):
    file: str
    line: Optional[int] = None
    description: str
    severity: Optional[str] = None
    bug_type: Optional[str] = None


class IdentifyRequest(BaseModel):
    findings: list[BugFinding]


class FindingJudgement(BaseModel):
    finding_index: int
    result: IdentifyResult
    explanation: str = ""
    confidence: float = 0.0


class IdentifyResponse(BaseModel):
    task_id: str
    status: TaskStatus
    total_findings: int
    matched_finding: Optional[int] = None
    judgements: list[FindingJudgement] = Field(default_factory=list)
    fix_source_dir: Optional[str] = None


# ---------------------------------------------------------------------------
# Task request / response
# ---------------------------------------------------------------------------

class TaskRequest(BaseModel):
    project: Optional[str] = None
    tier: HintTier = HintTier.T0
    agent_id: str = "default"


class TaskResponse(BaseModel):
    task_id: str
    instance_id: str
    project: str
    tier: HintTier
    hint: str
    repo_url: str
    commit: str
    build_recipe_url: str
    workspace_id: str
    created_at: datetime


# ---------------------------------------------------------------------------
# PoC submission (stage 2 — only after identification)
# ---------------------------------------------------------------------------

class SubmitRequest(BaseModel):
    poc: str
    harness: str
    bug_file: Optional[str] = None
    bug_function: Optional[str] = None
    bug_line: Optional[int] = None
    bug_description: Optional[str] = None


class SubmitResponse(BaseModel):
    task_id: str
    verdict: Verdict
    crash_output: str = ""
    fix_output: str = ""
    partial_credit: dict = Field(default_factory=dict)
    elapsed_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Task detail
# ---------------------------------------------------------------------------

class TaskDetail(BaseModel):
    task_id: str
    instance_id: str
    project: str
    tier: HintTier
    status: TaskStatus
    agent_id: str
    workspace_id: str = ""
    created_at: datetime
    identified_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    identification_result: Optional[IdentifyResult] = None
    num_findings: int = 0
    matched_finding_index: Optional[int] = None
    verdict: Optional[Verdict] = None
    partial_credit: dict = Field(default_factory=dict)
    elapsed_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Scoreboard
# ---------------------------------------------------------------------------

class AgentScore(BaseModel):
    agent_id: str
    total_tasks: int = 0
    identified: int = 0
    identification_failed: int = 0
    verified: int = 0
    exploit_failed: int = 0
    identification_rate: float = 0.0
    exploit_rate: float = 0.0
    avg_findings_per_task: float = 0.0
    avg_elapsed_seconds: float = 0.0
    by_project: dict = Field(default_factory=dict)
    by_tier: dict = Field(default_factory=dict)


class ScoreboardResponse(BaseModel):
    agents: list[AgentScore] = Field(default_factory=list)
    total_instances: int = 0
    total_tasks: int = 0
