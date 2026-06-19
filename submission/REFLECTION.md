# Reflection — Day 17

1. The most silent failure is decontamination. The repo still produces datasets, but the eval set stops being a real holdout. I would detect it by monitoring prompt overlap between `eval_golden.jsonl` and raw preference pairs; in this run, 3 raw pairs became 1 clean pair, so a sudden drop to 0 removals would be suspicious.

2. If I skip decontamination, I train on prompts the model is later graded on. That inflates offline metrics without improving generalization. The lie would look like strong results on the 2-row holdout, then weaker behavior on new customer-support phrasings.

3. A dangerous feature is customer `lifetime_spend`. In the repo’s leak example, the `u100` event on `2026-06-01` should only see `50.0`, but the naive join leaks `300.0`. In a real e-commerce support system, refund count or VIP tier would be just as dangerous.

4. The graph answers “Where does a widget ship from?” well because it needs the multihop path `widget -> accessory -> hanoi fulfillment center`. Flat chunk retrieval struggles when no single chunk contains both facts. The graph is overkill for a direct policy lookup like “How many days can I return a widget?”
