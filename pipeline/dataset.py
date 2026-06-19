"""Thực Hành 4 — Eval & preference datasets curated from agent traces.

Once agent turns live in Bronze (see traces.py), they become training data:

  * golden eval set   — (input -> reference output) from turns that SUCCEEDED.
  * preference pairs   — (prompt, chosen, rejected) where `chosen` is a good
                         answer and `rejected` is a failed/refused answer to the
                         SAME question. This is exactly the (x, y_w, y_l) format
                         DPO/ORPO consume on Day 22.

The decontamination step is the part students always skip and regret: any prompt
that appears in the eval set is removed from the preference (training) set, so we
never train on what we grade on. Train/test leakage is the #1 way an eval lies.
"""
from __future__ import annotations
import json
import unicodedata
from pathlib import Path

import duckdb

from .traces import BRONZE_SPANS


_VN_SUPPORT_HINTS = (
    "don hang",
    "đơn hàng",
    "o dau",
    "ở đâu",
    "doi tra",
    "đổi trả",
    "hoan tien",
    "hoàn tiền",
    "giao hang",
    "giao hàng",
    "van don",
    "vận đơn",
    "ho tro",
    "hỗ trợ",
)


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def build_eval_set(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Golden eval rows = the human-curated holdout (split='eval') of
    successful turns: {input, reference, trace_id}. Kept OUT of training."""
    rows = con.execute(
        f"""
        SELECT trace_id, user_input, agent_output
        FROM {BRONZE_SPANS}
        WHERE depth = 0 AND status = 'ok' AND split = 'eval'
              AND user_input IS NOT NULL AND agent_output IS NOT NULL
        ORDER BY trace_id
        """
    ).fetchall()
    return [
        {"trace_id": t, "input": i, "reference": o}
        for (t, i, o) in rows
    ]


def build_preference_pairs(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Pair a good (ok) answer with a bad (error) answer to the SAME question.

    `chosen`  = output of a successful turn for that input.
    `rejected` = output of a failed/refused turn for that same input.
    Yields the (prompt, chosen, rejected) triple DPO/ORPO expect (Day 22).
    """
    roots = con.execute(
        f"""
        SELECT user_input, status, agent_output
        FROM {BRONZE_SPANS}
        WHERE depth = 0 AND user_input IS NOT NULL
        """
    ).fetchall()

    good: dict[str, str] = {}
    bad: dict[str, str] = {}
    for user_input, status, output in roots:
        key = _norm(user_input)
        if status == "ok":
            good.setdefault(key, output)
        else:
            bad.setdefault(key, output)

    pairs = []
    for key in sorted(set(good) & set(bad)):
        pairs.append({"prompt": key, "chosen": good[key], "rejected": bad[key]})
    return pairs


def decontaminate(pairs: list[dict], eval_set: list[dict]) -> list[dict]:
    """Drop any preference pair whose prompt is also an eval input (no leakage).

    NOTE: this is EXACT-match decontamination (after lowercase + whitespace
    normalization). A reworded or paraphrased duplicate still leaks — production
    pipelines add n-gram (e.g. 13-gram) or embedding-similarity matching. See the
    'fuzzy decontamination' extension exercise.
    """
    held_out = {_norm(e["input"]) for e in eval_set}
    return [p for p in pairs if _norm(p["prompt"]) not in held_out]


def _norm_vn_support_text(s: str) -> str:
    """Heuristic normalization for Vietnamese e-commerce support prompts.

    This keeps the bonus small and intentionally favors common support traffic:
    accent-insensitive text, punctuation-insensitive order IDs, and collapsed
    whitespace so rewritten variants still overlap.
    """
    text = (s or "").replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = "".join(ch if ch.isalnum() else " " for ch in text)
    return " ".join(text.split())


def _looks_like_vn_support_text(s: str) -> bool:
    raw = _norm(s)
    fuzzy = _norm_vn_support_text(s)
    return any(hint in raw or hint in fuzzy for hint in _VN_SUPPORT_HINTS)


def decontaminate_vn_support_pairs(pairs: list[dict], eval_set: list[dict]) -> list[dict]:
    """Use exact match by default, with conservative VN support fuzzy matching."""
    held_out_exact = {_norm(e["input"]) for e in eval_set}
    held_out_support = {
        _norm_vn_support_text(e["input"])
        for e in eval_set
        if _looks_like_vn_support_text(e["input"])
    }

    clean = []
    for pair in pairs:
        prompt = pair["prompt"]
        if _norm(prompt) in held_out_exact:
            continue
        if _looks_like_vn_support_text(prompt) and _norm_vn_support_text(prompt) in held_out_support:
            continue
        clean.append(pair)
    return clean


def write_jsonl(rows: list[dict], path: Path) -> int:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(rows)
