"""LLM judge — evaluates whether agent findings match the target bug.

Uses OpenAI-compatible chat completions API (default: BigModel GLM-5.1).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import httpx

from server.models import (
    BugFinding,
    FindingJudgement,
    IdentifyResult,
    Instance,
)

logger = logging.getLogger(__name__)

# Default judge LLM config — override via env vars
DEFAULT_API_BASE = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
DEFAULT_MODEL = "glm-5.1"

JUDGE_SYSTEM = """\
You are a security vulnerability judge. You compare an agent's bug report \
against a known ground-truth vulnerability.

Ground truth:
- File: {file}
- Line: {line}
- Original code: {before}
- Mutated code: {after}
- Crash type: {crash_type}
- Explanation: {explanation}

For each agent finding, determine:
- "match": the finding clearly describes the same bug (right file, right area, \
  right root cause — exact line not required)
- "partial": the finding is in the right file or nearby code but misidentifies \
  the root cause or describes a different bug in the same function
- "no_match": the finding is about a different file, different code, or an \
  unrelated issue

Respond with ONLY a JSON array, one object per finding:
[{{"index": 0, "result": "match"|"partial"|"no_match", "confidence": 0.0-1.0, "explanation": "..."}}]

Be strict: a "match" means the agent genuinely found the target bug, not just \
any bug in the same file. But don't require the exact line number — if the agent \
describes the right logical issue in the right function, that's a match.\
"""

JUDGE_USER = """\
Agent reported {n} findings. Evaluate each:

{findings_text}\
"""


def _format_finding(i: int, f: BugFinding) -> str:
    parts = [f"Finding #{i}:"]
    parts.append(f"  File: {f.file}")
    if f.line is not None:
        parts.append(f"  Line: {f.line}")
    parts.append(f"  Description: {f.description}")
    if f.bug_type:
        parts.append(f"  Bug type: {f.bug_type}")
    if f.severity:
        parts.append(f"  Severity: {f.severity}")
    return "\n".join(parts)


async def judge_findings(
    instance: Instance,
    findings: list[BugFinding],
) -> list[FindingJudgement]:
    """Use LLM to judge each finding against the ground truth."""

    api_base = os.environ.get("JUDGE_API_BASE", DEFAULT_API_BASE)
    api_key = os.environ.get("JUDGE_API_KEY", "")
    model = os.environ.get("JUDGE_MODEL", DEFAULT_MODEL)

    if not api_key:
        logger.warning("no JUDGE_API_KEY set, falling back to heuristic judge")
        return _heuristic_judge(instance, findings)

    explanation = ""
    if hasattr(instance, "hints") and instance.hints.T2:
        explanation = instance.hints.T2

    system_msg = JUDGE_SYSTEM.format(
        file=instance.diff.file,
        line=instance.diff.line,
        before=instance.diff.before,
        after=instance.diff.after,
        crash_type=instance.crash_type,
        explanation=explanation,
    )

    findings_text = "\n\n".join(
        _format_finding(i, f) for i, f in enumerate(findings)
    )
    user_msg = JUDGE_USER.format(n=len(findings), findings_text=findings_text)

    # OpenAI-compatible chat completions request
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        "max_tokens": 2048,
        "temperature": 0.1,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(api_base, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

            # OpenAI-compatible response: choices[0].message.content
            text = data["choices"][0]["message"]["content"]
            logger.info("judge raw response: %s", text[:200])

            judgements = _parse_judge_response(text, len(findings))
            if judgements:
                return judgements

            logger.warning("failed to parse LLM response, falling back to heuristic")
            return _heuristic_judge(instance, findings)

    except Exception as e:
        logger.error("LLM judge failed: %s, falling back to heuristic", e)
        return _heuristic_judge(instance, findings)


def _parse_judge_response(text: str, n: int) -> list[FindingJudgement]:
    """Parse the LLM's JSON response into FindingJudgement objects."""
    start = text.find("[")
    end = text.rfind("]") + 1
    if start < 0 or end <= start:
        logger.warning("no JSON array in judge response")
        return []

    try:
        items = json.loads(text[start:end])
    except json.JSONDecodeError:
        logger.warning("failed to parse judge JSON: %s", text[start:end][:200])
        return []

    results = []
    for item in items:
        idx = item.get("index", 0)
        result_str = item.get("result", "no_match")
        try:
            result = IdentifyResult(result_str)
        except ValueError:
            result = IdentifyResult.NO_MATCH

        results.append(FindingJudgement(
            finding_index=idx,
            result=result,
            confidence=float(item.get("confidence", 0.0)),
            explanation=item.get("explanation", ""),
        ))

    return results


def _heuristic_judge(
    instance: Instance,
    findings: list[BugFinding],
) -> list[FindingJudgement]:
    """Fallback judge when LLM is unavailable — uses file/line matching."""
    target_file = Path(instance.diff.file).name
    target_line = instance.diff.line

    results = []
    for i, f in enumerate(findings):
        finding_file = Path(f.file).name if f.file else ""

        if finding_file == target_file:
            if f.line is not None and abs(f.line - target_line) <= 10:
                result = IdentifyResult.MATCH
                conf = 0.8
                expl = f"file match + line within 10 (delta={abs(f.line - target_line)})"
            elif f.line is not None and abs(f.line - target_line) <= 50:
                result = IdentifyResult.PARTIAL
                conf = 0.5
                expl = f"file match + line within 50 (delta={abs(f.line - target_line)})"
            else:
                result = IdentifyResult.PARTIAL
                conf = 0.3
                expl = "file match but line mismatch or not provided"
        else:
            result = IdentifyResult.NO_MATCH
            conf = 0.9
            expl = f"file mismatch: {finding_file} vs {target_file}"

        results.append(FindingJudgement(
            finding_index=i,
            result=result,
            confidence=conf,
            explanation=expl,
        ))

    return results
