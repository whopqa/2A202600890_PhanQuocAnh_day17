"""Tests for the agent-data flywheel + KG tracks (Thực Hành 1/3/4, §13). Zero-key."""
import duckdb
import pandas as pd
import pytest

from pipeline.traces import load_traces, flatten, traces_to_bronze, trace_summary, BRONZE_SPANS
from pipeline.dataset import (
    _norm_vn_support_text,
    build_eval_set,
    build_preference_pairs,
    decontaminate,
    decontaminate_vn_support_pairs,
)
from pipeline.features import point_in_time_features, naive_leaky_features
from pipeline.kg import extract_triples, build_graph, query, returnable_products
from pipeline import config


@pytest.fixture
def con():
    c = duckdb.connect(":memory:")
    traces_to_bronze(c, load_traces())
    yield c
    c.close()


def test_flatten_is_recursive():
    root = {"name": "invoke_agent", "trace_id": "x", "span_id": "r", "parent_id": None,
            "status": "ok", "duration_ms": 10,
            "children": [{"name": "chat", "span_id": "c", "parent_id": "r",
                          "status": "ok", "duration_ms": 5, "children": []}]}
    rows = flatten(root)
    assert len(rows) == 2                       # parent + child
    assert {r["depth"] for r in rows} == {0, 1}
    assert all(r["trace_id"] == "x" for r in rows)  # trace_id propagates to children


def test_bronze_has_one_row_per_span(con):
    (n,) = con.execute(f"SELECT count(*) FROM {BRONZE_SPANS}").fetchone()
    assert n == 21                              # total spans across the 8 seed traces


def test_trace_summary_one_row_per_trace(con):
    s = trace_summary(con)
    assert len(s) == 8
    assert set(s["outcome"]) == {"ok", "error"}


def test_eval_set_is_curated_holdout(con):
    ev = build_eval_set(con)
    assert len(ev) == 2                          # only split='eval' successful turns
    assert all(e["reference"] for e in ev)


def test_preference_pairs_have_chosen_and_rejected(con):
    pairs = build_preference_pairs(con)
    assert len(pairs) >= 1
    for p in pairs:
        assert p["chosen"] and p["rejected"] and p["chosen"] != p["rejected"]


def test_decontamination_removes_eval_leakage(con):
    ev = build_eval_set(con)
    pairs = build_preference_pairs(con)
    clean = decontaminate(pairs, ev)
    assert len(clean) < len(pairs)               # at least one overlap dropped
    held = {e["input"].lower() for e in ev}
    assert all(p["prompt"].lower() not in held for p in clean)


def test_vietnamese_decontamination_drops_rewritten_eval_overlap():
    eval_set = [
        {"trace_id": "t_eval", "input": "Đơn hàng #123 của tôi đang ở đâu?", "reference": "Đang giao"}
    ]
    pairs = [
        {"prompt": "Don hang 123 cua toi dang o dau", "chosen": "Đơn đang giao", "rejected": "Không rõ"},
        {"prompt": "Chính sách đổi trả cho widget là gì?", "chosen": "Đổi trả 30 ngày", "rejected": "Không hỗ trợ"},
    ]

    exact_clean = decontaminate(pairs, eval_set)
    assert exact_clean == pairs

    clean = decontaminate_vn_support_pairs(pairs, eval_set)
    assert clean == [
        {"prompt": "Chính sách đổi trả cho widget là gì?", "chosen": "Đổi trả 30 ngày", "rejected": "Không hỗ trợ"}
    ]


def test_vietnamese_decontamination_keeps_unrelated_non_latin_prompts():
    eval_set = [
        {"trace_id": "t_eval", "input": "客服 在 哪", "reference": "Ở trang hỗ trợ"}
    ]
    pairs = [
        {"prompt": "退貨 政策", "chosen": "Đổi trả 30 ngày", "rejected": "Không hỗ trợ"}
    ]

    assert _norm_vn_support_text(eval_set[0]["input"]) != _norm_vn_support_text(pairs[0]["prompt"])
    assert decontaminate_vn_support_pairs(pairs, eval_set) == pairs


def test_vietnamese_decontamination_preserves_exact_match_for_non_support_prompts():
    eval_set = [
        {"trace_id": "t_eval", "input": "C#", "reference": "language"}
    ]
    pairs = [
        {"prompt": "C++", "chosen": "language", "rejected": "unknown"}
    ]

    assert decontaminate(pairs, eval_set) == pairs
    assert decontaminate_vn_support_pairs(pairs, eval_set) == pairs


def test_flywheel_main_uses_vietnamese_aware_decontamination(monkeypatch):
    import flywheel

    eval_set = [
        {"trace_id": "t_eval", "input": "Đơn hàng #123 của tôi đang ở đâu?", "reference": "Đang giao"}
    ]
    pairs = [
        {"prompt": "Don hang 123 cua toi dang o dau", "chosen": "Đơn đang giao", "rejected": "Không rõ"}
    ]

    monkeypatch.setattr(flywheel, "load_traces", lambda: [])
    monkeypatch.setattr(flywheel, "traces_to_bronze", lambda con, traces: 0)
    monkeypatch.setattr(flywheel, "trace_summary", lambda con: pd.DataFrame([{"trace_id": "t1", "outcome": "ok"}]))
    monkeypatch.setattr(flywheel, "build_eval_set", lambda con: eval_set)
    monkeypatch.setattr(flywheel, "build_preference_pairs", lambda con: pairs)
    monkeypatch.setattr(
        flywheel,
        "point_in_time_features",
        lambda con: pd.DataFrame([{"user_id": "u1", "event_ts": "2024-01-01", "spend_at_event": 1}]),
    )
    monkeypatch.setattr(
        flywheel,
        "naive_leaky_features",
        lambda con: pd.DataFrame([{"user_id": "u1", "event_ts": "2024-01-01", "spend_leaky": 1}]),
    )
    monkeypatch.setattr(flywheel, "write_jsonl", lambda rows, path: len(rows))

    stats = flywheel.main()
    assert stats["n_pairs_raw"] == 1
    assert stats["n_pref"] == 0


def test_point_in_time_join_beats_leaky(con):
    pit = point_in_time_features(con)
    leaky = naive_leaky_features(con)
    m = pit.merge(leaky, on=["user_id", "event_ts"])
    # the naive join inflates at least one row by leaking a future spend value
    assert int((m["spend_leaky"] > m["spend_at_event"]).sum()) >= 1
    # ASOF never returns a value from after the event
    assert (m["spend_at_event"] <= m["spend_leaky"]).all()


def test_kg_extracts_clean_triples():
    triples = extract_triples(
        "Customers may return widgets within 30 days for a full refund. "
        "Gadgets carry a 90-day limited warranty. "
        "Sprockets are final sale and cannot be returned once opened."
    )
    rels = {(s, r) for s, r, _ in triples}
    assert ("widget", "RETURNABLE_WITHIN") in rels
    assert ("gadget", "HAS_WARRANTY") in rels
    assert ("sprocket", "NON_RETURNABLE") in rels


def test_kg_query_and_multi_node():
    graph = build_graph(extract_triples(config.DOCS_DIR.joinpath("sample.md").read_text()))
    assert query(graph, "widget", "RETURNABLE_WITHIN") == [("RETURNABLE_WITHIN", "30 days")]
    rp = returnable_products(graph)
    assert "widget" in rp            # has a return window
    assert "gadget" not in rp        # warranty is NOT returnability
    assert "sprocket" not in rp      # final sale


def test_kg_traverse_is_real_multihop():
    from pipeline.kg import ingest_docs_to_graph, traverse
    g = ingest_docs_to_graph(config.DOCS_DIR)
    hops = traverse(g, "widget", "SHIPS_FROM")
    assert hops, "expected a multi-hop path widget -> accessory -> warehouse"
    assert hops[0]["hops"] == 2                       # genuinely two hops, not one
    assert hops[0]["path"] == ["widget", "accessory", "hanoi fulfillment center"]
    assert "hanoi" in hops[0]["answer"].lower()


def test_vector_foil_fact_is_split_across_chunks():
    from pipeline.kg import vector_foil
    foil = vector_foil(config.DOCS_DIR, "widget", "hanoi")
    # the whole point: subject and answer live in DIFFERENT chunks
    assert foil["chunk_with_subject"] and foil["chunk_with_answer"]
    assert foil["chunk_with_subject"] != foil["chunk_with_answer"]
    assert foil["single_chunk_answers_it"] is False   # flat RAG cannot bridge
