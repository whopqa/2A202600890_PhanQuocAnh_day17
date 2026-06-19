# Day 17 Lab Completion Design

## Objective

Bring this repository to a submission-ready state for the scored Day 17 core lab plus the optional bonus challenge, without expanding scope into the optional dbt or Docker tracks. "Done" means the lite-path pipeline runs end to end, the expected artifacts are generated, the tests and smoke checks pass, and the repo contains a strong bonus brainstorm deliverable aligned with the grading rubric.

## Scope

Included:

- Core lite-path verification and fixes for `main.py`, `flywheel.py`, `kg_demo.py`, `verify.py`, and `pytest -q`
- Generation of required output artifacts such as `datasets/eval_golden.jsonl` and `datasets/preference_pairs.jsonl`
- Submission polish in files directly related to grading and handoff
- Bonus deliverable in `bonus/` for a Vietnamese e-commerce customer-support chatbot data-pipeline problem
- A minimal runnable prototype that demonstrates one key bonus design decision

Excluded:

- Optional dbt track
- Optional Docker / Airflow / Redpanda track
- Broad refactors unrelated to grading criteria
- Infrastructure or dependency changes that are not required for the lite path

## Recommended Approach

### Option A: Verify first, fix only what fails

Run the smoke checks and tests up front, then make the smallest code changes necessary to satisfy the rubric and produce artifacts.

Pros:

- Directly aligned with grading evidence
- Minimizes unnecessary edits
- Keeps risk low in an already-structured starter repo

Cons:

- Some issues may only appear after one fix unlocks a later stage

### Option B: Read the whole codebase and refactor proactively

Understand every pipeline module before making changes.

Pros:

- Maximizes global understanding
- May yield cleaner code

Cons:

- Slower
- High chance of changing non-essential code
- Poor fit for a rubric-driven lab

### Option C: Do the bonus first, then stabilize the core

Write the brainstorm and prototype first, then return to verification.

Pros:

- Useful if bonus is the real focus

Cons:

- Risks polishing optional work while core grading evidence is still unstable

## Decision

Choose Option A.

This repo already has the correct skeleton for the lab. The fastest and safest path is to use the executable checks as the truth source, repair only the broken pieces, then produce the bonus deliverables on top of a stable core. This approach also keeps the work tightly aligned with the rubric rather than drifting into optional improvements.

## Architecture and Change Boundaries

### Core execution flow

The repository is designed around two runnable flows:

1. Medallion pipeline:
   `raw_orders.csv -> Bronze -> validate/quarantine -> Silver dedup -> Gold aggregates`
2. Agent-data flywheel:
   `agent traces -> Bronze spans -> eval set + preference pairs -> decontamination -> point-in-time features`

The implementation work should preserve this structure. Changes should be limited to the modules that break those flows or prevent the expected artifacts from being written.

### Components likely to be touched

- `pipeline/validate.py` for data-contract and quarantine behavior
- `pipeline/transform.py` for Silver dedup or Gold aggregation correctness
- `pipeline/traces.py`, `pipeline/dataset.py`, and `pipeline/features.py` for the flywheel checks
- `pipeline/kg.py` or `kg_demo.py` if the KG verification path is incomplete
- `submission/REFLECTION.md` and `.gitignore` for handoff polish
- New `bonus/` files for the brainstorm and prototype

### Bonus prototype boundary

The prototype should extend the current flywheel rather than inventing a separate subsystem. The best fit is a Vietnamese e-commerce decontamination extension that shows why exact-match prompt filtering is insufficient for customer-support traffic. A lightweight implementation can demonstrate one of these:

- normalization-aware overlap detection for Vietnamese prompts
- simple rewrite-aware matching for order-status and return-policy questions
- a stricter holdout filter for prompts that differ only in casing, punctuation, or common support phrasing

This keeps the prototype connected to the existing `pipeline/dataset.py` logic and directly supports the bonus design narrative.

## Data Flow Design

### Core pipeline

The data path should remain append-friendly and easy to inspect:

- extract all raw rows into Bronze without mutation
- validate rows and quarantine failures without stopping the run
- build Silver from only clean rows, deduping by `order_id`
- aggregate Gold using only `completed` orders

### Flywheel pipeline

The agent data path should remain evaluation-safe:

- flatten nested traces into one Bronze row per span
- derive per-trace summaries for analyst visibility
- build eval rows from held-out successful traces only
- build preference pairs from good-vs-bad outcomes on the same prompt
- decontaminate any training pairs that overlap with the eval set
- demonstrate point-in-time correctness with `ASOF JOIN` and show the naive leak

### Bonus prototype flow

The prototype should add one extra curation step after raw preference-pair mining:

- start from the existing raw prompt pairs
- normalize Vietnamese customer-support prompts
- drop pairs whose normalized prompt overlaps the eval set even if the surface text differs slightly
- write or print a small example showing a pair that exact matching would keep but the improved filter removes

## Error Handling and Failure Semantics

The repo should favor non-destructive, repeatable behavior:

- validation failures go to quarantine rather than halting the whole run
- replayed streaming events remain idempotent
- generated artifacts are overwritten or regenerated deterministically for the current seed data
- verification should fail loudly when a rubric condition is not met

The implementation should not introduce hidden side effects outside the workspace and should avoid refactors that make reruns harder to reason about.

## Testing and Verification Design

Success should be proven through executable evidence, not inspection alone.

Primary checks:

- `python verify.py`
- `pytest -q`
- `python main.py`
- `python flywheel.py`
- `python kg_demo.py`

Expected verification goals:

- all 16 smoke checks pass
- pytest passes the existing suite
- output datasets are present after execution
- the bonus prototype is runnable or directly exercised by a test or small entrypoint

If the bonus prototype changes curation behavior, it should get one focused automated test so the reasoning is encoded as behavior rather than only described in prose.

## Deliverables

### Required graded outputs

- Passing lite-path code and tests
- Generated dataset artifacts in `datasets/`
- A clean and reviewable submission state

### Bonus outputs

- `bonus/DESIGN.md` with at least 600 words
- 4 to 6 chosen open questions, each answered with a concrete tradeoff and decision
- At least one rejected alternative with a reason
- An architecture sketch
- At least one decision explicitly grounded in Vietnamese-language support traffic, cost, or failure semantics
- A minimal runnable prototype tied to the bonus design

## Open Assumptions

- The environment already has or can install the lite-path Python dependencies
- The user wants practical completion over optional expansion
- Bonus quality matters, but not at the expense of destabilizing the core lab

## Final Design Summary

We will complete the lab by stabilizing the existing lite-path implementation first, using the repo's own smoke tests and pytest suite as the source of truth. After the core passes, we will generate the required artifacts, then add a tightly scoped bonus package centered on a Vietnamese e-commerce customer-support chatbot flywheel. The bonus will combine a strong design write-up with a small runnable prototype that extends decontamination beyond exact-match prompts, because that is both realistic for customer-support traffic and deeply connected to the lab's main lesson about leakage.
