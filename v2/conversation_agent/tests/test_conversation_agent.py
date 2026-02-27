"""
Integration tests for the Conversation Agent.
One test per item in the Verification Checklist.

Requires ANTHROPIC_API_KEY to be set in .env or the environment.
Run from the conversation_agent/ directory:
    pytest tests/test_conversation_agent.py -v
"""

import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import pytest

# Allow importing from the parent directory (conversation_agent/) when run
# as `pytest tests/` from any working directory.
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from conversation_agent import run  # noqa: E402 — must come after sys.path and dotenv

TODAY = date.today().strftime("%Y%m%d")

# ─── Shared fixtures ──────────────────────────────────────────────────────────

CLEAN_PRD = """\
# TaskFlow — Product Requirements Document

## Actors
- **Employee**: A registered user who creates and tracks personal tasks.
- **System**: The TaskFlow backend service.

## REQ-001: Task Creation
The System shall allow an authenticated Employee to create a task with the following
required fields: title (5–150 characters), due date (ISO 8601, must be today or future),
priority (Low, Medium, or High), and an optional description (max 500 characters).

Acceptance Criteria:
- Given valid task data, when the Employee submits the form, then the System saves the task
  and returns HTTP 201 with the task UUID within 2 seconds.
- Given a due date in the past, when the Employee submits, then the System returns HTTP 400
  with "Due date must be today or a future date."
- Given a title shorter than 5 characters, when the Employee submits, then the System returns
  HTTP 400 with "Title must be at least 5 characters."

## REQ-002: Task Completion
The System shall allow an authenticated Employee to mark any of their own tasks as complete.
The completion timestamp must be recorded in UTC.

Acceptance Criteria:
- Given an incomplete task owned by the Employee, when the Employee marks it complete, then
  the System sets status to "completed", records the UTC timestamp, and returns HTTP 200.
- Given a task owned by a different Employee, when the Employee attempts to mark it complete,
  then the System returns HTTP 403 with "You do not have permission to modify this task."
"""

AMBIGUOUS_PRD = """\
We need a task management app. It should be fast and easy to use.
Users should be able to add tasks and see them. Maybe add due dates later.
The admin can delete stuff. It should work well on all devices.
Performance should be good. Security is important somehow.
"""

# Minimal artifact set covering TC-003 and TC-004, used across review mode tests.
SAMPLE_ARTIFACTS = {
    "requirements": [
        {
            "req_id": "REQ-001",
            "title": "User Login",
            "description": "Users must be able to log in with email and password.",
        }
    ],
    "risk_output": {
        "test_cases": [
            {
                "tc_id": "TC-003",
                "objective": "Verify login with valid credentials redirects to dashboard",
                "priority": "P2",
                "priority_basis": (
                    "Medium-risk: login failure is recoverable via password reset flow"
                ),
                "severity": "high",
                "severity_basis": (
                    "Authentication blocking — failure prevents all platform access"
                ),
                "type": "e2e",
                "surface": "ui",
                "reasoning": (
                    "Priority P2 because a recovery path exists; "
                    "severity high because auth failure blocks all access"
                ),
            },
            {
                "tc_id": "TC-004",
                "objective": "Verify login page renders correctly on mobile viewport",
                "priority": "P2",
                "priority_basis": "Visual regression with clear workaround via desktop access",
                "severity": "medium",
                "severity_basis": "Secondary journey — UI degradation with workaround available",
                "type": "e2e",
                "surface": "ui",
                "reasoning": "Mobile rendering is important but not blocking for release",
            },
        ]
    },
}

# Review-mode artifacts: same as SAMPLE_ARTIFACTS but includes the original run's
# request_id so _run_review() can locate the run directory and save revision_request.json.
REVIEW_ARTIFACTS = {
    "request_id": f"RUN-{TODAY}-001",
    **SAMPLE_ARTIFACTS,
}


# ─── Test environment helpers ─────────────────────────────────────────────────


def _setup_gen_env(tmp_path, monkeypatch):
    """Point RUNS_DIR at tmp_path/runs so generation writes to a temp dir.

    With this setup:
      - runs/  → tmp_path/runs/
      - .current_run → tmp_path/.current_run   (parent of RUNS_DIR)
    """
    monkeypatch.setenv("RUNS_DIR", str(tmp_path / "runs"))


def _setup_review_run(tmp_path, monkeypatch):
    """Set up a complete fake active run for review mode tests.

    Creates:
      - tmp_path/runs/RUN-{TODAY}-001/generation_request.json  (contains REVIEW_ARTIFACTS)
      - tmp_path/.current_run                                  (contains "RUN-{TODAY}-001")
    Also sets RUNS_DIR → tmp_path/runs so all filesystem I/O stays inside tmp_path.
    """
    run_id = f"RUN-{TODAY}-001"
    runs_dir = tmp_path / "runs"
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "generation_request.json").write_text(
        json.dumps(REVIEW_ARTIFACTS), encoding="utf-8"
    )
    (tmp_path / ".current_run").write_text(run_id + "\n", encoding="utf-8")
    monkeypatch.setenv("RUNS_DIR", str(runs_dir))


# ─── Generation Mode Tests ────────────────────────────────────────────────────


def test_generation_clean_prd(tmp_path, monkeypatch):
    """Checklist item 1: Given a clean PRD → prd_type is 'clean'."""
    _setup_gen_env(tmp_path, monkeypatch)
    result = run(mode="generate", prd_text=CLEAN_PRD)
    assert result.get("prd_type") == "clean", (
        f"Expected prd_type='clean' for a well-structured PRD with "
        f"actors, testable requirements, and acceptance criteria. Got: {result.get('prd_type')}"
    )


def test_generation_ambiguous_prd(tmp_path, monkeypatch):
    """Checklist item 2: Given a vague/ambiguous PRD → prd_type is 'ambiguous'."""
    _setup_gen_env(tmp_path, monkeypatch)
    result = run(mode="generate", prd_text=AMBIGUOUS_PRD)
    assert result.get("prd_type") == "ambiguous", (
        f"Expected prd_type='ambiguous' for a PRD with vague language and no acceptance criteria. "
        f"Got: {result.get('prd_type')}"
    )


def test_generation_temperature_always_zero(tmp_path, monkeypatch):
    """Checklist item 3: temperature is always 0, regardless of run_config."""
    _setup_gen_env(tmp_path, monkeypatch)
    result = run(
        mode="generate",
        prd_text=CLEAN_PRD,
        run_config={"temperature": 1, "custom_override": "ignored"},
    )
    assert result["constraints"]["temperature"] == 0, (
        f"Expected constraints.temperature=0 (non-negotiable). "
        f"Got: {result['constraints']['temperature']}"
    )


def test_generation_allow_regeneration_always_false(tmp_path, monkeypatch):
    """Checklist item 4: allow_regeneration is always false, regardless of run_config."""
    _setup_gen_env(tmp_path, monkeypatch)
    result = run(
        mode="generate",
        prd_text=CLEAN_PRD,
        run_config={"allow_regeneration": True},
    )
    assert result["constraints"]["allow_regeneration"] is False, (
        f"Expected constraints.allow_regeneration=False (non-negotiable). "
        f"Got: {result['constraints']['allow_regeneration']}"
    )


def test_generation_request_id_format(tmp_path, monkeypatch):
    """Checklist item 5: request_id follows RUN-YYYYMMDD-NNN format with today's date.
    Also verifies that .current_run is written to the project root (parent of RUNS_DIR)
    and contains the matching request_id.
    """
    _setup_gen_env(tmp_path, monkeypatch)
    result = run(mode="generate", prd_text=CLEAN_PRD)
    request_id = result.get("request_id", "")
    assert re.match(r"^RUN-\d{8}-\d{3}$", request_id), (
        f"Expected RUN-YYYYMMDD-NNN format (e.g. RUN-{TODAY}-001). Got: '{request_id}'"
    )
    assert TODAY in request_id, (
        f"Expected today's date ({TODAY}) in request_id. Got: '{request_id}'"
    )
    # .current_run must be written to tmp_path (the parent of RUNS_DIR=tmp_path/runs)
    current_run_file = tmp_path / ".current_run"
    assert current_run_file.exists(), (
        ".current_run was not written after a successful generation run"
    )
    assert current_run_file.read_text(encoding="utf-8").strip() == request_id, (
        f".current_run content '{current_run_file.read_text().strip()}' "
        f"does not match request_id '{request_id}'"
    )


def test_generation_empty_prd_returns_error_object(tmp_path, monkeypatch):
    """Checklist item 6: Empty PRD returns error object — agent does not crash."""
    _setup_gen_env(tmp_path, monkeypatch)
    result = run(mode="generate", prd_text="")
    assert "error" in result, (
        f"Expected an 'error' key in the result for empty PRD. Got keys: {list(result.keys())}"
    )
    assert result.get("mode") == "generate", (
        f"Expected mode='generate' in error response. Got: {result.get('mode')}"
    )
    # Must not be a raised exception — verified by reaching this line


# ─── Review Mode — Intent Classification Tests ───────────────────────────────


def test_review_intent_explain(tmp_path, monkeypatch):
    """Checklist item 7: 'Why is TC-003 P2?' → intent=explain, TC-003 in targets, no changes."""
    _setup_review_run(tmp_path, monkeypatch)
    result = run(
        mode="review",
        reviewer_message="Why is TC-003 P2?",
        # current_artifacts omitted — auto-loaded from .current_run
    )
    assert result["intent"] == "explain", (
        f"Expected intent='explain' for a why-question. Got: '{result['intent']}'"
    )
    assert "TC-003" in result["explanation_targets"], (
        f"Expected 'TC-003' in explanation_targets. Got: {result['explanation_targets']}"
    )
    assert result["requested_changes"] == [], (
        f"Expected empty requested_changes for explain-only intent. "
        f"Got: {result['requested_changes']}"
    )


def test_review_intent_revise(tmp_path, monkeypatch):
    """Checklist item 8: 'Make TC-004 P1 — login is critical.' → intent=revise with correct change."""
    _setup_review_run(tmp_path, monkeypatch)
    result = run(
        mode="review",
        reviewer_message="Make TC-004 P1 — login is critical.",
        # current_artifacts omitted — auto-loaded from .current_run
    )
    assert result["intent"] == "revise", (
        f"Expected intent='revise' for an explicit change request. Got: '{result['intent']}'"
    )
    assert len(result["requested_changes"]) == 1, (
        f"Expected exactly 1 requested change. Got: {len(result['requested_changes'])}"
    )
    change = result["requested_changes"][0]
    assert change["target_id"] == "TC-004", (
        f"Expected target_id='TC-004'. Got: '{change['target_id']}'"
    )
    assert change["field"] == "priority", (
        f"Expected field='priority'. Got: '{change['field']}'"
    )
    assert change["new_value"] == "P1", (
        f"Expected new_value='P1'. Got: '{change['new_value']}'"
    )
    assert result["explanation_targets"] == [], (
        f"Expected empty explanation_targets for revise-only intent. "
        f"Got: {result['explanation_targets']}"
    )


def test_review_intent_both(tmp_path, monkeypatch):
    """Checklist item 9: 'Why is TC-003 P2? Also bump TC-004 to P1.' → intent=both."""
    _setup_review_run(tmp_path, monkeypatch)
    result = run(
        mode="review",
        reviewer_message="Why is TC-003 P2? Also bump TC-004 to P1.",
        # current_artifacts omitted — auto-loaded from .current_run
    )
    assert result["intent"] == "both", (
        f"Expected intent='both' for a message with both a question and a change. "
        f"Got: '{result['intent']}'"
    )
    assert "TC-003" in result["explanation_targets"], (
        f"Expected 'TC-003' in explanation_targets. Got: {result['explanation_targets']}"
    )
    changes = result["requested_changes"]
    tc004_priority_change = next(
        (
            c for c in changes
            if c.get("target_id") == "TC-004"
            and c.get("field") == "priority"
            and c.get("new_value") == "P1"
        ),
        None,
    )
    assert tc004_priority_change is not None, (
        f"Expected a requested_change for TC-004/priority/P1. Got: {changes}"
    )


def test_review_forbidden_field_rejected(tmp_path, monkeypatch):
    """Checklist item 10: 'Change the tc_id on TC-004' → requested_changes=[], tc_id rejected."""
    _setup_review_run(tmp_path, monkeypatch)
    result = run(
        mode="review",
        reviewer_message="Change the tc_id on TC-004",
        # current_artifacts omitted — auto-loaded from .current_run
    )
    assert result["requested_changes"] == [], (
        f"Expected empty requested_changes for a forbidden-field request. "
        f"Got: {result['requested_changes']}"
    )
    rejected = result["rejected_changes"]
    assert len(rejected) >= 1, (
        f"Expected at least one rejected_change for the tc_id request. Got: {rejected}"
    )
    tc_id_rejection = next(
        (r for r in rejected if r.get("field") == "tc_id"), None
    )
    assert tc_id_rejection is not None, (
        f"Expected a rejection entry with field='tc_id'. Got rejections: {rejected}"
    )
    assert "forbidden" in tc_id_rejection["reason"].lower() or "cannot" in tc_id_rejection["reason"].lower(), (
        f"Expected the rejection reason to explain 'tc_id' is forbidden. "
        f"Got: '{tc_id_rejection['reason']}'"
    )


def test_review_invalid_enum_value_rejected(tmp_path, monkeypatch):
    """Checklist item 11: 'Set TC-004 priority to P9' → rejected with invalid enum reason."""
    _setup_review_run(tmp_path, monkeypatch)
    result = run(
        mode="review",
        reviewer_message="Set TC-004 priority to P9",
        # current_artifacts omitted — auto-loaded from .current_run
    )
    rejected = result["rejected_changes"]
    assert len(rejected) >= 1, (
        f"Expected at least one rejected_change for the P9 request. Got: {rejected}"
    )
    # The rejection should mention P9 or the invalid value or valid alternatives
    priority_rejection = next(
        (
            r for r in rejected
            if r.get("field") == "priority" or "P9" in r.get("reason", "")
        ),
        None,
    )
    assert priority_rejection is not None, (
        f"Expected a rejection for priority/P9. Got rejections: {rejected}"
    )
    reason = priority_rejection.get("reason", "").lower()
    assert any(
        keyword in reason
        for keyword in ["p9", "invalid", "valid", "p1", "p2", "p3"]
    ), (
        f"Expected rejection reason to reference P9 or valid values (P1, P2, P3). "
        f"Got: '{priority_rejection['reason']}'"
    )


# ─── Review Mode — Policy Enforcement Tests ──────────────────────────────────


def test_review_policy_delta_only_always_true(tmp_path, monkeypatch):
    """Checklist item 12: policy.delta_only is always true in output."""
    _setup_review_run(tmp_path, monkeypatch)
    result = run(
        mode="review",
        reviewer_message="Why is TC-003 P2?",
        # current_artifacts omitted — auto-loaded from .current_run
    )
    assert result["policy"]["delta_only"] is True, (
        f"Expected policy.delta_only=True (non-negotiable). "
        f"Got: {result['policy']['delta_only']}"
    )


def test_review_policy_disallow_unrequested_always_true(tmp_path, monkeypatch):
    """Checklist item 13: policy.disallow_unrequested_changes is always true in output."""
    _setup_review_run(tmp_path, monkeypatch)
    result = run(
        mode="review",
        reviewer_message="Why is TC-003 P2?",
        # current_artifacts omitted — auto-loaded from .current_run
    )
    assert result["policy"]["disallow_unrequested_changes"] is True, (
        f"Expected policy.disallow_unrequested_changes=True (non-negotiable). "
        f"Got: {result['policy']['disallow_unrequested_changes']}"
    )


def test_review_request_id_format(tmp_path, monkeypatch):
    """Checklist item 14: request_id follows REV-YYYYMMDD-NNN format with today's date."""
    _setup_review_run(tmp_path, monkeypatch)
    result = run(
        mode="review",
        reviewer_message="Why is TC-003 P2?",
        # current_artifacts omitted — auto-loaded from .current_run
    )
    request_id = result.get("request_id", "")
    assert re.match(r"^REV-\d{8}-\d{3}$", request_id), (
        f"Expected REV-YYYYMMDD-NNN format (e.g. REV-{TODAY}-001). Got: '{request_id}'"
    )
    assert TODAY in request_id, (
        f"Expected today's date ({TODAY}) in request_id. Got: '{request_id}'"
    )


# ─── Both Modes Tests ─────────────────────────────────────────────────────────


def test_output_is_pure_json_no_markdown(tmp_path, monkeypatch):
    """Checklist item 15: Output is a plain dict — no markdown fences, no prose wrapping."""
    _setup_gen_env(tmp_path, monkeypatch)
    gen_result = run(mode="generate", prd_text=CLEAN_PRD)
    assert isinstance(gen_result, dict), (
        f"Generation output must be a dict, not {type(gen_result).__name__}"
    )
    gen_json = json.dumps(gen_result)
    # json.dumps succeeds without error (output is JSON-serializable)
    assert isinstance(gen_json, str)
    assert "```" not in gen_json, "Generation output JSON contains markdown code fences"

    # gen wrote .current_run → review auto-loads the generation artifacts from it
    rev_result = run(
        mode="review",
        reviewer_message="Why is TC-003 P2?",
        # current_artifacts omitted — auto-loaded from .current_run written by gen above
    )
    assert isinstance(rev_result, dict), (
        f"Review output must be a dict, not {type(rev_result).__name__}"
    )
    rev_json = json.dumps(rev_result)
    assert isinstance(rev_json, str)
    assert "```" not in rev_json, "Review output JSON contains markdown code fences"


def test_no_crash_on_missing_optional_fields(tmp_path, monkeypatch):
    """Checklist item 16: Agent does not crash when optional fields are omitted."""
    _setup_gen_env(tmp_path, monkeypatch)
    # Generation mode — no optional args (no existing_suite_index_path, no run_config)
    gen_result = run(mode="generate", prd_text=CLEAN_PRD)
    assert isinstance(gen_result, dict), "Generation must return a dict even without optional args"
    assert "request_id" in gen_result or "error" in gen_result, (
        "Generation result must contain 'request_id' or 'error'"
    )

    # Review mode — no optional args: no current_artifacts (auto-loaded from .current_run
    # written by gen above) and no decision_log (intentionally omitted)
    rev_result = run(
        mode="review",
        reviewer_message="Why is TC-003 P2?",
    )
    assert isinstance(rev_result, dict), "Review must return a dict even without decision_log"
    assert "request_id" in rev_result, "Review result must contain 'request_id'"


# ─── Execution Plan Tests ──────────────────────────────────────────────────────


def test_execution_plan_saved_for_revise_intent(tmp_path, monkeypatch):
    """execution_plan.json is saved for intent=revise with correct structure.

    Covers:
      - File is written to the correct run folder
      - change_scope has at least one entry
      - forbidden_changes is the hard-coded constant list
      - validation_profile is the hard-coded constant list
    """
    _setup_review_run(tmp_path, monkeypatch)
    run(
        mode="review",
        reviewer_message="Make TC-004 P1 — login is critical.",
        # current_artifacts omitted — auto-loaded from .current_run
    )
    run_id = f"RUN-{TODAY}-001"
    ep_file = tmp_path / "runs" / run_id / "execution_plan.json"

    assert ep_file.exists(), (
        "execution_plan.json was not written to the run folder for intent=revise"
    )
    ep = json.loads(ep_file.read_text(encoding="utf-8"))

    assert len(ep["change_scope"]) >= 1, (
        f"Expected at least one entry in change_scope for a revise request. "
        f"Got: {ep['change_scope']}"
    )
    assert ep["forbidden_changes"] == ["req_id", "tc_id", "objective", "type", "surface"], (
        f"Expected hard-coded forbidden_changes constant. Got: {ep['forbidden_changes']}"
    )
    assert ep["validation_profile"] == ["schema", "cross_ref", "delta", "rationale"], (
        f"Expected hard-coded validation_profile constant. Got: {ep['validation_profile']}"
    )


def test_execution_plan_not_created_for_explain_intent(tmp_path, monkeypatch):
    """execution_plan.json is NOT created when intent=explain (no changes to scope)."""
    _setup_review_run(tmp_path, monkeypatch)
    run(
        mode="review",
        reviewer_message="Why is TC-003 P2?",
        # current_artifacts omitted — auto-loaded from .current_run
    )
    run_id = f"RUN-{TODAY}-001"
    ep_file = tmp_path / "runs" / run_id / "execution_plan.json"

    assert not ep_file.exists(), (
        "execution_plan.json should NOT be created when intent=explain"
    )
