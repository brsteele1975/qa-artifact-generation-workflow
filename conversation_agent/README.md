# Conversation Agent

The human-facing portal for QRAFT v2 — a multi-agent system that takes a Product Requirements Document (PRD) and produces a structured, traceable test plan.

This is the first agent in the pipeline. It handles two modes: generating a structured request from a raw PRD, and processing reviewer feedback into scoped change instructions for the Builder Agent.

**Part of the QRAFT v2 system in progress. Builder Agent is next.**

---

## What It Does

**Generation mode** — Takes a PRD (clean or messy) and produces a `generation_request.json` in a timestamped run folder. This is the input the Builder Agent reads to produce requirements and test cases.

**Review mode** — Takes a plain-language reviewer message, classifies the intent (`explain` / `revise` / `both`), and produces two artifacts:
- `revision_request.json` — structured change instructions
- `execution_plan.json` — scoped authorization for what the Builder Agent is allowed to modify

---

## Requirements

- Python 3.9+
- An OpenAI API key

```bash
cp .env.example .env
# Add your OPENAI_API_KEY to .env
pip install -r requirements.txt
```

---

## Usage

**Generate a test plan request from a PRD:**
```bash
make gen PRD=sample_input/your_prd.md
```

**Submit a reviewer message:**
```bash
make review MSG="Change TC-004 priority to P1 because it covers a payment flow"
```

**Check the current run status:**
```bash
make status
```

**Run the test suite:**
```bash
make test
```

---

## Output Structure

Every run creates a folder under `runs/`:

```
runs/
  RUN-20260227-001/
    prd.md                    ← copy of the input PRD
    generation_request.json   ← structured request for Builder Agent
    revision_request.json     ← populated after make review
    execution_plan.json       ← populated after make review (revise/both intent)
```

The active run is tracked in `.current_run`. Review mode reads this automatically — no need to pass a run ID manually.

---

## Test Suite

18 tests covering generation mode, review mode, intent classification, sequence counters, and filesystem isolation.

```bash
make test
```

---

## Part of the QRAFT v2 Pipeline

```
PRD → [Conversation Agent] → generation_request.json
                           → revision_request.json + execution_plan.json
                                        ↓
                              [Builder Agent]        ← next
                                        ↓
                              [Validators x4]
                                        ↓
                              [Critic Agent]
                                        ↓
                              test_plan.md
```