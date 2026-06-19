# Day 17 Lab Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the lite-path Day 17 lab to a submission-ready state with passing verification, generated datasets, a polished reflection, and a bonus package for a Vietnamese e-commerce customer-support chatbot.

**Architecture:** Keep the repo's existing two-lane structure intact: the Medallion pipeline stays responsible for orders quality, dedup, and Gold aggregates, while the flywheel path stays responsible for traces, eval data, preference pairs, and point-in-time correctness. Limit code changes to broken rubric paths and add the bonus prototype as a small extension to dataset decontamination rather than as a new subsystem.

**Tech Stack:** Python 3.10+, DuckDB, Pandas, Pandera, pytest, Markdown docs

---

## File Map

- Modify: `main.py`
- Modify: `flywheel.py`
- Modify: `verify.py`
- Modify: `pipeline/validate.py`
- Modify: `pipeline/transform.py`
- Modify: `pipeline/traces.py`
- Modify: `pipeline/dataset.py`
- Modify: `pipeline/features.py`
- Modify: `pipeline/kg.py`
- Modify: `tests/test_pipeline.py`
- Modify: `tests/test_flywheel.py`
- Modify: `submission/REFLECTION.md`
- Modify: `.gitignore`
- Create: `bonus/DESIGN.md`
- Create: `bonus/prototype_demo.py`
- Create: `datasets/eval_golden.jsonl`
- Create: `datasets/preference_pairs.jsonl`

### Task 1: Baseline Verification and Capture the First Real Failures

**Files:**
- Modify: none
- Test: `verify.py`
- Test: `tests/test_pipeline.py`
- Test: `tests/test_flywheel.py`

- [ ] **Step 1: Run the smoke test and capture the first failing path**

Run:

```powershell
python verify.py
```

Expected:

```text
=== verify.py: Day 17 lab smoke test ===
...
RESULT: <n>/16 checks — FAILURES ABOVE
```

- [ ] **Step 2: Run pytest to capture failing unit tests separately from the smoke test**

Run:

```powershell
pytest -q
```

Expected:

```text
...F...
=========================== short test summary info ===========================
FAILED tests/...
```

- [ ] **Step 3: Record the runtime evidence that will guide every later code edit**

Use this checklist while reading failures:

```text
1. If main.py fails first, inspect pipeline/validate.py and pipeline/transform.py.
2. If flywheel checks fail, inspect pipeline/traces.py, pipeline/dataset.py, and pipeline/features.py.
3. If kg_demo.py or KG tests fail, inspect pipeline/kg.py only after the core and flywheel failures are understood.
4. Do not edit tests yet unless the intended bonus prototype requires a new dedicated test.
```

- [ ] **Step 4: Confirm the failure reproduction path is stable before changing code**

Run:

```powershell
python main.py
python flywheel.py
python kg_demo.py
```

Expected:

```text
At least one command fails or produces output inconsistent with verify.py / pytest failures.
```

- [ ] **Step 5: Commit the untouched baseline context if a commit history checkpoint is needed**

```bash
git add docs/superpowers/specs/2026-06-19-day17-lab-completion-design.md docs/superpowers/plans/2026-06-19-day17-lab-completion.md
git commit -m "docs: add day17 completion spec and plan"
```

### Task 2: Repair Core Lite-Path Behavior Until Verification Passes

**Files:**
- Modify: `main.py`
- Modify: `verify.py`
- Modify: `pipeline/validate.py`
- Modify: `pipeline/transform.py`
- Modify: `pipeline/traces.py`
- Modify: `pipeline/dataset.py`
- Modify: `pipeline/features.py`
- Modify: `pipeline/kg.py`
- Test: `tests/test_pipeline.py`
- Test: `tests/test_flywheel.py`

- [ ] **Step 1: Make the first failing behavior explicit in a focused test if coverage is missing**

If the failure is not already pinned by an existing test, add a focused assertion in the appropriate test file. Example shape for dataset behavior:

```python
def test_decontamination_removes_eval_leakage(con):
    ev = build_eval_set(con)
    pairs = build_preference_pairs(con)
    clean = decontaminate(pairs, ev)
    assert len(clean) < len(pairs)
    held = {e["input"].lower() for e in ev}
    assert all(p["prompt"].lower() not in held for p in clean)
```

- [ ] **Step 2: Run only the failing test or smoke-path command**

Run one tight command based on the failure source:

```powershell
pytest tests/test_pipeline.py -q
pytest tests/test_flywheel.py -q
python verify.py
```

Expected:

```text
The selected command still fails for the same reason and gives a short edit-feedback loop.
```

- [ ] **Step 3: Apply the minimal production code fix in the relevant module**

Follow these exact fix patterns rather than refactoring broadly:

```python
def validate(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    try:
        clean = ORDER_SCHEMA.validate(df, lazy=True)
        return clean.reset_index(drop=True), df.iloc[0:0].copy()
    except pa.errors.SchemaErrors as err:
        bad_index = sorted({int(i) for i in err.failure_cases["index"].dropna()})
        quarantined = df.loc[df.index.isin(bad_index)].copy()
        clean = df.loc[~df.index.isin(bad_index)].copy()
        clean = ORDER_SCHEMA.validate(clean.reset_index(drop=True), lazy=True)
        return clean.reset_index(drop=True), quarantined.reset_index(drop=True)
```

```python
def decontaminate(pairs: list[dict], eval_set: list[dict]) -> list[dict]:
    held_out = {_norm(e["input"]) for e in eval_set}
    return [p for p in pairs if _norm(p["prompt"]) not in held_out]
```

```python
def point_in_time_features(con: duckdb.DuckDBPyConnection) -> "pd.DataFrame":
    _seed(con)
    return con.execute(
        """
        SELECT e.user_id, e.event_ts, f.lifetime_spend AS spend_at_event
        FROM events e
        ASOF LEFT JOIN feature_history f
          ON e.user_id = f.user_id AND e.event_ts >= f.valid_from
        ORDER BY e.user_id, e.event_ts
        """
    ).fetchdf()
```

- [ ] **Step 4: Re-run the narrow verification command until the repaired behavior passes**

Run:

```powershell
pytest tests/test_pipeline.py -q
pytest tests/test_flywheel.py -q
```

Expected:

```text
All tests in the previously failing file pass.
```

- [ ] **Step 5: Run full lite-path verification**

Run:

```powershell
python verify.py
python main.py
python flywheel.py
python kg_demo.py
pytest -q
```

Expected:

```text
RESULT: 16/16 checks — ALL PASS
18 passed
```

- [ ] **Step 6: Commit the core stabilization work**

```bash
git add main.py flywheel.py verify.py pipeline/validate.py pipeline/transform.py pipeline/traces.py pipeline/dataset.py pipeline/features.py pipeline/kg.py tests/test_pipeline.py tests/test_flywheel.py
git commit -m "fix: stabilize day17 lite pipeline and flywheel"
```

### Task 3: Add the Bonus Prototype for Vietnamese E-commerce Decontamination

**Files:**
- Modify: `pipeline/dataset.py`
- Modify: `tests/test_flywheel.py`
- Create: `bonus/prototype_demo.py`

- [ ] **Step 1: Write the failing test for normalized Vietnamese prompt overlap**

Add this test to `tests/test_flywheel.py`:

```python
def test_vietnamese_decontamination_drops_rewritten_eval_overlap():
    eval_set = [
        {"trace_id": "t_eval", "input": "Đơn hàng #123 của tôi đang ở đâu?", "reference": "Đang giao"}
    ]
    pairs = [
        {"prompt": "Don hang 123 cua toi dang o dau", "chosen": "Đơn đang giao", "rejected": "Không rõ"},
        {"prompt": "Chính sách đổi trả cho widget là gì?", "chosen": "Đổi trả 30 ngày", "rejected": "Không hỗ trợ"},
    ]
    clean = decontaminate_vn_support_pairs(pairs, eval_set)
    assert clean == [
        {"prompt": "Chính sách đổi trả cho widget là gì?", "chosen": "Đổi trả 30 ngày", "rejected": "Không hỗ trợ"}
    ]
```

- [ ] **Step 2: Run the new test to verify the prototype behavior is missing**

Run:

```powershell
pytest tests/test_flywheel.py::test_vietnamese_decontamination_drops_rewritten_eval_overlap -q
```

Expected:

```text
FAILED ... NameError: name 'decontaminate_vn_support_pairs' is not defined
```

- [ ] **Step 3: Implement normalization-aware decontamination in `pipeline/dataset.py`**

Add these functions:

```python
import re
import unicodedata


def _norm_vn_support_text(s: str) -> str:
    text = unicodedata.normalize("NFKD", s or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\border\b", "don hang", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def decontaminate_vn_support_pairs(pairs: list[dict], eval_set: list[dict]) -> list[dict]:
    held_out = {_norm_vn_support_text(e["input"]) for e in eval_set}
    return [p for p in pairs if _norm_vn_support_text(p["prompt"]) not in held_out]
```

- [ ] **Step 4: Add a tiny runnable demo for the prototype**

Create `bonus/prototype_demo.py`:

```python
from pipeline.dataset import decontaminate, decontaminate_vn_support_pairs


def main() -> dict:
    eval_set = [
        {"trace_id": "t_eval", "input": "Đơn hàng #123 của tôi đang ở đâu?", "reference": "Đang giao"}
    ]
    pairs = [
        {"prompt": "Don hang 123 cua toi dang o dau", "chosen": "Đơn đang giao", "rejected": "Không rõ"},
        {"prompt": "Chính sách đổi trả cho widget là gì?", "chosen": "Đổi trả 30 ngày", "rejected": "Không hỗ trợ"},
    ]
    exact_clean = decontaminate(pairs, eval_set)
    vn_clean = decontaminate_vn_support_pairs(pairs, eval_set)
    print("=== Bonus prototype: VN decontamination ===")
    print(f"exact-match keeps  : {len(exact_clean)} pairs")
    print(f"vn-normalized keeps: {len(vn_clean)} pairs")
    return {"exact_pairs": len(exact_clean), "vn_pairs": len(vn_clean)}


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run the prototype verification**

Run:

```powershell
pytest tests/test_flywheel.py::test_vietnamese_decontamination_drops_rewritten_eval_overlap -q
python bonus/prototype_demo.py
```

Expected:

```text
1 passed
=== Bonus prototype: VN decontamination ===
exact-match keeps  : 2 pairs
vn-normalized keeps: 1 pairs
```

- [ ] **Step 6: Commit the bonus prototype**

```bash
git add pipeline/dataset.py tests/test_flywheel.py bonus/prototype_demo.py
git commit -m "feat: add vietnamese support decontamination prototype"
```

### Task 4: Generate Submission Artifacts and Polish the Hand-off

**Files:**
- Modify: `submission/REFLECTION.md`
- Modify: `.gitignore`
- Create: `bonus/DESIGN.md`
- Create: `datasets/eval_golden.jsonl`
- Create: `datasets/preference_pairs.jsonl`

- [ ] **Step 1: Regenerate the graded artifacts from the stabilized pipeline**

Run:

```powershell
python flywheel.py
python main.py
python kg_demo.py
```

Expected:

```text
datasets/eval_golden.jsonl and datasets/preference_pairs.jsonl exist and reflect the current code.
```

- [ ] **Step 2: Write the bonus brainstorm document**

Create `bonus/DESIGN.md` with this structure:

```markdown
# Bonus Challenge: Vietnamese E-commerce CSKH Flywheel

## Problem and Constraints
- chatbot supports order-status, return-policy, and refund questions
- traffic is Vietnamese, noisy, and often repeats the same intent with different wording
- eval leakage is easy because support prompts are templatic

## Chosen Questions and Decisions
### 1. Sources and shape
Decision: use batch trace exports first, not real-time ingestion
Tradeoff: lower freshness, much lower operational cost

### 2. Batch vs streaming
Decision: nightly curation for eval/train, streaming only for product telemetry
Tradeoff: avoids overbuilding a low-volume support workflow

### 3. Contracts and quality
Decision: quarantine malformed traces and keep raw spans append-only
Tradeoff: more storage, much safer debugging

### 4. Flywheel leakage
Decision: normalized Vietnamese decontamination before preference-pair release
Tradeoff: a few good pairs are dropped, but offline eval stays trustworthy

### 5. Failure semantics
Decision: idempotent reruns and overwrite-derived datasets
Tradeoff: simpler reproducibility, less history in derived artifacts

## Rejected Alternative
- full embedding-similarity decontamination on every run
- rejected because it adds cost and complexity before exact and normalized matching are exhausted

## Architecture Sketch
```text
chatbot traces -> bronze spans -> trace summary
                         |-> eval holdout
                         |-> raw preference pairs -> VN decontamination -> train pairs
orders/events -> PIT features ------------------------------------^
```
```

- [ ] **Step 3: Replace the reflection template with concise, concrete answers**

Target answer style for `submission/REFLECTION.md`:

```markdown
1. The silent failure is decontamination, because the pipeline still "works" while the eval set is contaminated. I would monitor prompt-overlap rates between eval and train pairs and alert if overlap rises above zero.

2. If I skip decontamination, the model trains on examples it will later be graded on, so offline win rates and exact-match scores look better than real generalization. The lie would show up as strong eval metrics but weak behavior on new prompts.

3. In e-commerce support, a dangerous feature is customer lifetime spend or refund count. If I join the latest value instead of the value known at the event time, the model learns from future information.

4. The graph answers "Where does a widget ship from?" because that needs two linked facts. A flat vector lookup is enough for a direct question like "What is the return window for a widget?"
```

- [ ] **Step 4: Keep noisy local-only files out of the submission**

Ensure `.gitignore` contains these lines if they are missing:

```gitignore
.venv/
__pycache__/
.pytest_cache/
warehouse.duckdb
quarantine.csv
```

- [ ] **Step 5: Run the final full verification pass**

Run:

```powershell
python verify.py
pytest -q
python bonus/prototype_demo.py
```

Expected:

```text
RESULT: 16/16 checks — ALL PASS
18 passed
prototype demo prints exact vs VN-normalized pair counts
```

- [ ] **Step 6: Commit the submission-ready state**

```bash
git add .gitignore submission/REFLECTION.md bonus/DESIGN.md bonus/prototype_demo.py datasets/eval_golden.jsonl datasets/preference_pairs.jsonl
git commit -m "docs: finalize day17 submission artifacts"
```

## Self-Review

- Spec coverage: the plan covers core verification, code repair, artifact generation, bonus reasoning, and submission polish.
- Placeholder scan: all tasks reference exact files, commands, and target behavior; no TODO/TBD markers remain.
- Type consistency: the bonus prototype uses `list[dict]` shapes consistent with the existing dataset functions and test style.
