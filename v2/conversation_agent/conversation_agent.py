"""
Conversation Agent — LLM-powered interface for test plan generation and review.

Operates in two modes:
  generate : Receives a PRD and produces a structured generation_request.json
  review   : Receives a reviewer message and produces a revision_request.json

Usage (CLI):
  python conversation_agent.py --mode generate --prd path/to/prd.md
  python conversation_agent.py --mode generate --prd stdin   # read PRD from stdin
  python conversation_agent.py --mode review --message "Why is TC-003 P2?" --artifacts artifacts.json

Usage (module):
  from conversation_agent import run
  result = run(mode="generate", prd_text="...")
  result = run(mode="review", reviewer_message="...", current_artifacts={...})
"""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from prompts import execution_plan_prompt, generation_prompt, intent_prompt, revision_prompt
from schemas import ExecutionPlan, GenerationRequest, IntentClassification, RevisionRequest

load_dotenv()


# ─── Internal helpers ─────────────────────────────────────────────────────────


def _get_llm() -> ChatOpenAI:
    """Initialize and return the LLM. Raises EnvironmentError if API key is missing."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY environment variable is not set. "
            "Copy .env.example to .env and add your API key, "
            "or export OPENAI_API_KEY=<your-key> in your shell."
        )
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    return ChatOpenAI(model=model, api_key=api_key)


def _today() -> str:
    """Return today's date as a YYYYMMDD string."""
    return date.today().strftime("%Y%m%d")


def _format_suite_path(path: Optional[str]) -> str:
    """
    Format the existing_suite_index_path value for the generation prompt.
    Returns the quoted path string, or the instruction to use null.
    """
    if path:
        return f'"{path}"'
    return "null (JSON null — no path was provided; set this field to null, not the string 'null')"


# ─── Public API ───────────────────────────────────────────────────────────────


def run(
    mode: str,
    prd_text: Optional[str] = None,
    existing_suite_index_path: Optional[str] = None,
    run_config: Optional[dict] = None,
    reviewer_message: Optional[str] = None,
    current_artifacts: Optional[dict] = None,
    decision_log: Optional[list] = None,
) -> dict:
    """
    Run the Conversation Agent in the specified mode.

    Args:
        mode: "generate" or "review"
        prd_text: Raw PRD text content (generation mode)
        existing_suite_index_path: Optional path to existing test suite index (generation mode)
        run_config: Optional runtime configuration overrides (generation mode)
        reviewer_message: Natural language message from a human reviewer (review mode)
        current_artifacts: Current artifact set including test_cases[] (review mode)
        decision_log: Prior revision history entries for request_id sequencing (review mode)

    Returns:
        dict: Structured output as a plain Python dict (JSON-serializable)
    """
    if mode == "generate":
        return _run_generate(
            prd_text=prd_text,
            existing_suite_index_path=existing_suite_index_path,
            run_config=run_config or {},
        )
    elif mode == "review":
        return _run_review(
            reviewer_message=reviewer_message,
            current_artifacts=current_artifacts,  # None → auto-load from .current_run
            decision_log=decision_log or [],
        )
    else:
        raise ValueError(f"Unknown mode: '{mode}'. Must be 'generate' or 'review'.")


# ─── Mode implementations ─────────────────────────────────────────────────────


def _run_generate(
    prd_text: Optional[str],
    existing_suite_index_path: Optional[str],
    run_config: dict,
) -> dict:
    """Execute generation mode: PRD → GenerationRequest.

    Side effects:
      - Creates runs/{request_id}/ directory (RUNS_DIR env var overrides base, default "runs")
      - Writes raw PRD text to runs/{request_id}/prd.md
      - Writes generation_request.json to runs/{request_id}/generation_request.json
    """
    # Guard: empty or whitespace-only PRD — return error object, do not crash
    if not prd_text or not prd_text.strip():
        return {"error": "PRD input is empty or could not be parsed", "mode": "generate"}

    include_duplicate_scan = run_config.get("include_duplicate_scan", True)
    today = _today()

    # Pre-generate the request_id so we can name the run directory before the LLM call.
    # Scan runs/ for existing RUN-{today}-NNN folders and increment from the highest.
    runs_base = Path(os.environ.get("RUNS_DIR", "runs"))
    prefix = f"RUN-{today}-"
    existing = [
        int(p.name[len(prefix):])
        for p in runs_base.glob(f"{prefix}*")
        if p.is_dir() and p.name[len(prefix):].isdigit()
    ] if runs_base.exists() else []
    next_seq = (max(existing) + 1) if existing else 1
    request_id = f"RUN-{today}-{next_seq:03d}"

    # Create the run directory and save the raw PRD text.
    run_dir = runs_base / request_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "prd.md").write_text(prd_text, encoding="utf-8")

    # prd_source is always the canonical runs-relative path.
    prd_source = f"runs/{request_id}/prd.md"

    llm = _get_llm()

    # LCEL chain: generation_prompt | llm.with_structured_output(GenerationRequest)
    generation_chain = generation_prompt | llm.with_structured_output(GenerationRequest)

    result: GenerationRequest = generation_chain.invoke(
        {
            "prd_text": prd_text,
            "prd_source": prd_source,
            "today": today,
            "include_duplicate_scan": str(include_duplicate_scan).lower(),
            "existing_suite_index_path": _format_suite_path(existing_suite_index_path),
        }
    )

    output = result.model_dump()

    # Pin request_id and prd_source to the Python-computed values.
    # The LLM prompt uses a static "001" placeholder; overriding here ensures
    # the output JSON always matches the actual run directory on disk.
    output["request_id"] = request_id
    output["prd_source"] = prd_source

    # Save generation_request.json alongside the PRD in the run directory.
    (run_dir / "generation_request.json").write_text(
        json.dumps(output, indent=2), encoding="utf-8"
    )

    # Mark this as the active run: write request_id to .current_run in the project root
    # (the directory that contains the runs/ folder, i.e. the parent of RUNS_DIR).
    project_root = runs_base.parent
    (project_root / ".current_run").write_text(request_id + "\n", encoding="utf-8")

    return output


def _run_review(
    reviewer_message: Optional[str],
    current_artifacts: Optional[dict],
    decision_log: list,
) -> dict:
    """Execute review mode: reviewer message → RevisionRequest (two-step LCEL chains).

    current_artifacts may be None; when omitted the function auto-loads from .current_run:
      1. Reads project_root/.current_run to get the active request_id
      2. Loads runs/{request_id}/generation_request.json as the artifact set
    Raises RuntimeError if neither current_artifacts nor .current_run exists.

    Side effects:
      - If current_artifacts contains a "request_id" (the original RUN-… ID), writes
        revision_request.json to runs/{original_request_id}/revision_request.json
        (RUNS_DIR env var overrides base, default "runs")
    """
    if not reviewer_message or not reviewer_message.strip():
        raise ValueError("reviewer_message is required and cannot be empty in review mode.")

    today = _today()

    # runs_base and project_root are shared by the auto-load logic and the REV counter.
    runs_base = Path(os.environ.get("RUNS_DIR", "runs"))
    project_root = runs_base.parent

    # Auto-load artifacts from .current_run when not explicitly provided.
    if current_artifacts is None:
        current_run_file = project_root / ".current_run"
        if not current_run_file.exists():
            raise RuntimeError(
                "No active run found. Run make gen first, or pass --artifacts explicitly."
            )
        active_run_id = current_run_file.read_text(encoding="utf-8").strip()
        artifacts_file = runs_base / active_run_id / "generation_request.json"
        if not artifacts_file.exists():
            raise FileNotFoundError(
                f"Artifacts not found for active run '{active_run_id}': {artifacts_file}"
            )
        current_artifacts = json.loads(artifacts_file.read_text(encoding="utf-8"))

    # REV sequence counter: scan all subdirs of runs/ for existing revision_request.json
    # files and collect request_id values that start with "REV-{today}-".
    rev_prefix = f"REV-{today}-"
    existing_revs: list[int] = []
    if runs_base.exists():
        for subdir in runs_base.iterdir():
            if subdir.is_dir():
                rev_file = subdir / "revision_request.json"
                if rev_file.exists():
                    try:
                        data = json.loads(rev_file.read_text(encoding="utf-8"))
                        rid = data.get("request_id", "")
                        suffix = rid[len(rev_prefix):]
                        if rid.startswith(rev_prefix) and suffix.isdigit():
                            existing_revs.append(int(suffix))
                    except (json.JSONDecodeError, OSError):
                        pass
    next_rev_seq = (max(existing_revs) + 1) if existing_revs else 1
    rev_request_id = f"REV-{today}-{next_rev_seq:03d}"
    seq = f"{next_rev_seq:03d}"

    # The original RUN-… request_id from the artifacts file, used to locate the save path.
    original_run_id: Optional[str] = current_artifacts.get("request_id")

    llm = _get_llm()

    # Step 1 LCEL chain: intent_prompt | llm.with_structured_output(IntentClassification)
    intent_chain = intent_prompt | llm.with_structured_output(IntentClassification)
    intent_result: IntentClassification = intent_chain.invoke(
        {"reviewer_message": reviewer_message}
    )

    # Step 2 LCEL chain: revision_prompt | llm.with_structured_output(RevisionRequest)
    # Pass the Step 1 intent classification as context into Step 2.
    revision_chain = revision_prompt | llm.with_structured_output(RevisionRequest)
    result: RevisionRequest = revision_chain.invoke(
        {
            "reviewer_message": reviewer_message,
            "current_artifacts": json.dumps(current_artifacts, indent=2),
            "intent": intent_result.intent,
            "today": today,
            "seq": seq,
            "decision_log": json.dumps(decision_log, indent=2),
        }
    )

    output = result.model_dump()

    # Pin request_id to the Python-computed REV ID (LLM prompt uses a static placeholder).
    output["request_id"] = rev_request_id

    # Save revision_request.json alongside the original run's artifacts (if known).
    if original_run_id:
        run_dir = runs_base / original_run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "revision_request.json").write_text(
            json.dumps(output, indent=2), encoding="utf-8"
        )

        # Generate execution_plan.json when the intent involves changes (revise or both).
        # Skipped for explain-only intent — no change scope to define.
        if output.get("intent") in ("revise", "both"):
            ep_chain = execution_plan_prompt | llm.with_structured_output(ExecutionPlan)
            ep_result: ExecutionPlan = ep_chain.invoke(
                {
                    "requested_changes": json.dumps(
                        output.get("requested_changes", []), indent=2
                    ),
                }
            )
            ep_output = ep_result.model_dump()

            # Inject hard-coded constants — the LLM is not trusted to generate these.
            ep_output["forbidden_changes"] = [
                "req_id", "tc_id", "objective", "type", "surface"
            ]
            ep_output["validation_profile"] = [
                "schema", "cross_ref", "delta", "rationale"
            ]

            (run_dir / "execution_plan.json").write_text(
                json.dumps(ep_output, indent=2), encoding="utf-8"
            )
            print(json.dumps(ep_output, indent=2))

    return output


# ─── CLI entry point ──────────────────────────────────────────────────────────


def main() -> None:
    """CLI entry point. Run with --help for usage."""
    parser = argparse.ArgumentParser(
        prog="conversation_agent",
        description="Conversation Agent for test plan generation and review.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  # Generation mode — from file
  python conversation_agent.py --mode generate --prd path/to/prd.md

  # Generation mode — from stdin
  cat path/to/prd.md | python conversation_agent.py --mode generate --prd stdin

  # Generation mode — with optional overrides
  python conversation_agent.py --mode generate --prd path/to/prd.md \\
      --suite-index path/to/suite_index.json \\
      --run-config '{"include_duplicate_scan": false}'

  # Review mode
  python conversation_agent.py --mode review \\
      --message "Why is TC-003 P2?" \\
      --artifacts path/to/artifacts.json

  # Review mode — with decision log for sequence numbering
  python conversation_agent.py --mode review \\
      --message "Make TC-004 P1 — login is critical." \\
      --artifacts artifacts.json \\
      --decision-log decision_log.json
""",
    )
    parser.add_argument(
        "-m", "--mode",
        required=True,
        choices=["generate", "review"],
        help="Operating mode: 'generate' (PRD → request) or 'review' (message → revision).",
    )

    # Generation mode arguments
    gen_group = parser.add_argument_group("Generation mode options")
    gen_group.add_argument(
        "-p", "--prd",
        help="Path to a PRD markdown or text file, or the string 'stdin' to read from standard input.",
    )
    gen_group.add_argument(
        "--suite-index",
        dest="suite_index",
        help="Path to an existing test suite index file (optional).",
    )
    gen_group.add_argument(
        "--run-config",
        dest="run_config",
        help='JSON string of runtime config overrides, e.g. \'{"include_duplicate_scan": false}\'.',
    )

    # Review mode arguments
    rev_group = parser.add_argument_group("Review mode options")
    rev_group.add_argument(
        "-msg", "--message", help="Reviewer's natural language message (required for review mode)."
    )
    rev_group.add_argument(
        "-a", "--artifacts",
        help="Path to current artifacts JSON file (required for review mode).",
    )
    rev_group.add_argument(
        "--decision-log",
        dest="decision_log",
        help="Path to decision log JSON file for request_id sequence numbering (optional).",
    )

    args = parser.parse_args()
    kwargs: dict[str, Any] = {}

    if args.mode == "generate":
        if not args.prd:
            parser.error("--prd <path> is required in generate mode (use --prd stdin to read from standard input).")

        if args.prd == "stdin":
            if sys.stdin.isatty():
                parser.error("--prd stdin requires piped input, but stdin is a terminal.")
            kwargs["prd_text"] = sys.stdin.read()
        else:
            prd_path = Path(args.prd)
            if not prd_path.exists():
                parser.error(f"PRD file not found: {args.prd}")
            kwargs["prd_text"] = prd_path.read_text(encoding="utf-8")

        if args.suite_index:
            kwargs["existing_suite_index_path"] = args.suite_index

        if args.run_config:
            try:
                kwargs["run_config"] = json.loads(args.run_config)
            except json.JSONDecodeError as exc:
                parser.error(f"--run-config is not valid JSON: {exc}")

    elif args.mode == "review":
        if not args.message:
            parser.error("--message is required in review mode.")
        kwargs["reviewer_message"] = args.message

        if args.artifacts:
            artifacts_path = Path(args.artifacts)
            if not artifacts_path.exists():
                parser.error(f"Artifacts file not found: {args.artifacts}")
            kwargs["current_artifacts"] = json.loads(artifacts_path.read_text(encoding="utf-8"))
        # else: current_artifacts defaults to None → _run_review auto-loads from .current_run

        if args.decision_log:
            log_path = Path(args.decision_log)
            if not log_path.exists():
                parser.error(f"Decision log file not found: {args.decision_log}")
            kwargs["decision_log"] = json.loads(log_path.read_text(encoding="utf-8"))

    result = run(mode=args.mode, **kwargs)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
