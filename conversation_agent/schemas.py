"""
All Pydantic v2 input/output schemas for the Conversation Agent.

Every field has a type annotation and a Field(description="...") — the description
is what the LLM sees when producing structured output via .with_structured_output().
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ─── Generation Mode Schemas ──────────────────────────────────────────────────


class GenerationConstraints(BaseModel):
    temperature: int = Field(
        description=(
            "LLM temperature setting for generation. "
            "Must always be exactly 0 (integer zero), regardless of any run_config override attempt."
        )
    )
    allow_regeneration: bool = Field(
        description=(
            "Whether regeneration of the test suite is allowed. "
            "Must always be exactly false, regardless of any run_config override attempt."
        )
    )
    include_duplicate_scan: bool = Field(
        description=(
            "Whether to include a duplicate test case scan in the generation pipeline. "
            "Default is true. Can be overridden via run_config."
        )
    )


class GenerationArtifacts(BaseModel):
    existing_suite_index_path: Optional[str] = Field(
        default=None,
        description=(
            "Path to an existing test suite index file to use as generation context. "
            "Must be null (JSON null) if no path was provided — not the string 'null', "
            "but a true JSON null value."
        ),
    )


class GenerationRequest(BaseModel):
    request_id: str = Field(
        description=(
            "Unique request identifier. "
            "Format: RUN-YYYYMMDD-NNN where YYYYMMDD is today's date and NNN is a "
            "zero-padded three-digit sequence number. "
            "Use the exact date and sequence number provided in the prompt."
        )
    )
    mode: Literal["generate"] = Field(
        description="The operating mode. Must always be the exact string 'generate'."
    )
    prd_source: str = Field(
        description=(
            "The source of the PRD input. "
            "Use 'inline' if the PRD was provided as raw pasted text. "
            "Use the filename (not the full path) if a file path was provided. "
            "Use the exact value specified in the prompt."
        )
    )
    prd_type: Literal["clean", "ambiguous"] = Field(
        description=(
            "Classification of the PRD's requirement quality. "
            "'clean': requirements are specific, testable, and unambiguous; "
            "actors are explicitly defined; acceptance criteria are present and measurable; "
            "no contradictions exist. "
            "'ambiguous': requirements are vague or imprecise; actors are missing or unclear; "
            "acceptance criteria are absent or unmeasurable; requirements contradict each other. "
            "When uncertain between 'clean' and 'ambiguous', always choose 'ambiguous'."
        )
    )
    constraints: GenerationConstraints = Field(
        description="Non-negotiable runtime constraints for the generation process."
    )
    artifacts: GenerationArtifacts = Field(
        description="Artifact paths and references used during generation."
    )


# ─── Review Mode Schemas ──────────────────────────────────────────────────────


class IntentClassification(BaseModel):
    intent: Literal["explain", "revise", "both"] = Field(
        description=(
            "The classified intent of the reviewer's message. "
            "'explain': reviewer is asking WHY a decision was made; no change is requested; "
            "indicators include question words (why, how, what, explain, tell me). "
            "'revise': reviewer is explicitly requesting a SPECIFIC CHANGE to the test plan; "
            "indicators include action words (make, change, update, set, move, bump, add, remove). "
            "'both': the same message contains both a question about a decision AND an explicit "
            "request for a change. "
            "When ambiguous, always prefer 'explain' over 'revise'."
        )
    )


class RequestedChange(BaseModel):
    target_id: str = Field(
        description=(
            "The TC-* or REQ-* identifier of the artifact being changed. "
            "Must reference an ID that exists in current_artifacts."
        )
    )
    field: str = Field(
        description=(
            "The specific field being changed. "
            "Must be one of the allowed fields: "
            "priority, priority_basis, human_note, severity, severity_basis, reasoning."
        )
    )
    new_value: str = Field(
        description=(
            "The requested new value for the field. "
            "For 'priority': must be exactly P1, P2, or P3. "
            "For 'severity': must be exactly high, medium, or low."
        )
    )
    reason: str = Field(
        description=(
            "The reason for the change. "
            "Copy the reviewer's exact verbatim wording if a reason was provided. "
            "If no reason was stated, use the exact string 'Requested by reviewer.'"
        )
    )


class RejectedChange(BaseModel):
    target_id: str = Field(
        description=(
            "The TC-* or REQ-* identifier whose change request was rejected. "
            "Use the ID as stated by the reviewer."
        )
    )
    field: str = Field(
        description="The field that the reviewer requested to change, but which was rejected."
    )
    reason: str = Field(
        description=(
            "Plain-language explanation of why the change was rejected. "
            "Be specific: state whether it is a forbidden field, an invalid enum value, "
            "or an unresolvable ID. Examples: "
            "'tc_id is a forbidden field and cannot be changed.' "
            "'P9 is not a valid priority value. Valid values are: P1, P2, P3.'"
        )
    )


class RevisionPolicy(BaseModel):
    delta_only: bool = Field(
        description=(
            "Whether only the explicitly requested changes are applied. "
            "Must always be exactly true. This is non-negotiable."
        )
    )
    disallow_unrequested_changes: bool = Field(
        description=(
            "Whether unrequested changes are disallowed. "
            "Must always be exactly true. This is non-negotiable."
        )
    )


class RevisionRequest(BaseModel):
    request_id: str = Field(
        description=(
            "Unique request identifier. "
            "Format: REV-YYYYMMDD-NNN where YYYYMMDD is today's date and NNN is a "
            "zero-padded three-digit sequence number. "
            "Use the exact date and sequence number provided in the prompt."
        )
    )
    mode: Literal["revise"] = Field(
        description="The operating mode. Must always be the exact string 'revise'."
    )
    intent: Literal["explain", "revise", "both"] = Field(
        description="The classified intent of the reviewer's message, as pre-determined."
    )
    target_artifact: Literal["test_plan"] = Field(
        description="The artifact being targeted. Must always be the exact string 'test_plan'."
    )
    requested_changes: list[RequestedChange] = Field(
        description=(
            "List of validated, machine-readable change instructions. "
            "Must be an empty list [] if intent is 'explain' only. "
            "Only includes changes that passed validation (allowed field, valid enum, resolvable ID)."
        )
    )
    explanation_targets: list[str] = Field(
        description=(
            "List of TC-* or REQ-* IDs the reviewer is asking about. "
            "Must be an empty list [] if intent is 'revise' only. "
            "Extract all artifact IDs explicitly mentioned in the message."
        )
    )
    rejected_changes: list[RejectedChange] = Field(
        description=(
            "List of changes the reviewer requested that were rejected. "
            "Include one entry per rejected change. "
            "Reasons for rejection: forbidden field, invalid enum value, or unresolvable ID. "
            "Must be an empty list [] if nothing was rejected."
        )
    )
    policy: RevisionPolicy = Field(
        description=(
            "Non-negotiable policy constraints for this revision. "
            "Both delta_only and disallow_unrequested_changes must always be true."
        )
    )


# ─── Execution Plan Schemas ───────────────────────────────────────────────────


class ChangeScope(BaseModel):
    target_id: str = Field(
        description=(
            "The TC-* or REQ-* identifier of the artifact being changed. "
            "Matches a target_id from the revision request's requested_changes."
        )
    )
    allowed_fields: list[str] = Field(
        description=(
            "The specific fields that may be modified for this target. "
            "Derived from all field values for this target_id in the requested_changes list."
        )
    )


class ExecutionPlan(BaseModel):
    change_scope: list[ChangeScope] = Field(
        description=(
            "One entry per unique target_id found in the requested_changes. "
            "Each entry lists the allowed_fields that may be modified for that target."
        )
    )
    forbidden_changes: list[str] = Field(
        description=(
            "Fields that must NEVER be modified, regardless of any request. "
            "Will be overridden with hard-coded constants after LLM generation — "
            "output any placeholder list (e.g. [])."
        )
    )
    validation_profile: list[str] = Field(
        description=(
            "Validators to run after the Builder applies the patch. "
            "Will be overridden with hard-coded constants after LLM generation — "
            "output any placeholder list (e.g. [])."
        )
    )
