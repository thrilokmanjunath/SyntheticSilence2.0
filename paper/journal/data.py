"""
Confusion-matrix data for the journal draft, and every metric derived from it.

Rows are gold labels (SUPPORTS, REFUTES, NOT ENOUGH INFO). Columns are predicted labels
(SUPPORTS, REFUTES, NOT ENOUGH INFO, MIXED). Counts come from
results/verdict_eval/{baseline_pooled_run1,pooled_wiki_run1,stance_wiki_run1}/predictions.jsonl
(100 FEVER claims; seed 42; same claims in every variant).
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

GOLD = ["SUPPORTS", "REFUTES", "NEI"]
PRED = ["SUPPORTS", "REFUTES", "NEI", "MIXED"]

CONFUSION: Dict[str, List[List[int]]] = {
    "Pooled, OpenAlex": [[15, 9, 9, 0], [3, 31, 2, 0], [2, 24, 5, 0]],
    "Pooled, Wikipedia": [[24, 8, 1, 0], [4, 31, 1, 0], [6, 25, 0, 0]],
    "Stance, Wikipedia": [[22, 2, 8, 1], [13, 12, 10, 1], [9, 3, 19, 0]],
}


def wilson(k: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def metrics(m: List[List[int]]) -> Dict[str, object]:
    n = sum(map(sum, m))
    correct = sum(m[i][i] for i in range(3))
    row = [sum(m[i]) for i in range(3)]
    col = [sum(m[g][p] for g in range(3)) for p in range(3)]
    prec = [m[i][i] / col[i] if col[i] else 0.0 for i in range(3)]
    rec = [m[i][i] / row[i] if row[i] else 0.0 for i in range(3)]
    f1 = [2 * p * r / (p + r) if p + r else 0.0 for p, r in zip(prec, rec)]
    decisive_n = row[0] + row[1]
    decisive_k = m[0][0] + m[1][1]
    return {
        "n": n,
        "accuracy": correct / n,
        "accuracy_ci": wilson(correct, n),
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "macro_f1": sum(f1) / 3,
        "decisive_accuracy": decisive_k / decisive_n,
        "decisive_ci": wilson(decisive_k, decisive_n),
        "decisive_n": decisive_n,
        "row_sums": row,
        "mixed": sum(m[i][3] for i in range(3)),
    }


def row_normalised(m: List[List[int]]) -> List[List[float]]:
    return [[v / sum(r) if sum(r) else 0.0 for v in r] for r in m]


def latex_matrix(m: List[List[object]], fmt: str = "{}") -> str:
    body = r" \\ ".join(" & ".join(fmt.format(v) for v in r) for r in m)
    return r"\begin{bmatrix} " + body + r" \end{bmatrix}"
