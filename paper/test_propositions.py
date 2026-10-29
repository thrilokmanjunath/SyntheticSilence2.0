"""
Machine checks for every proposition and every matrix-derived number in the journal draft.

These are not proofs; the proofs are in the paper. They fail loudly if a statement in the paper
stops matching the code that the paper describes (the real `aggregate`, `DensityEstimator`,
scikit-learn's LedoitWolf), or if a number in a table stops matching its confusion matrix.
"""
import itertools
import math
import random
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).parent / "journal"))

from app.models.schemas import ConstructionFamily, Evidence  # noqa: E402
from app.services.algo.density import DensityEstimator  # noqa: E402
from app.services.algo.stance import (  # noqa: E402
    CONFIDENCE_FLOOR, STRONG_SINGLE, AssessedSource, aggregate,
)
from app.services.algo.uncertainty import SimilarityDistributionEntropy  # noqa: E402
import data  # noqa: E402

EV = Evidence(id="e", text="source text", construction_family=ConstructionFamily.ambiguous_claim)
CONFS = [0.3, 0.5, 0.79, 0.8, 0.95]


def src(stance, conf, quote=True):
    q = "a verbatim quote" if quote and stance in ("supports", "refutes") else None
    return AssessedSource(EV, stance, conf, q)


def options():
    out = []
    for stance in ("supports", "refutes"):
        for c in CONFS:
            for quote in (True, False):
                out.append((stance, c, quote))
    for stance in ("neutral", "irrelevant"):
        for c in CONFS:
            out.append((stance, c, False))
    return out


OPTS = options()


def build(cfg):
    return [src(*o) for o in cfg]


def counted(cfg, side):
    return [c for (s, c, q) in cfg if s == side and c >= CONFIDENCE_FLOOR and q]


def Q(confs):
    return len(confs) >= 2 or (len(confs) == 1 and confs[0] >= STRONG_SINGLE)


def swap(cfg):
    flip = {"supports": "refutes", "refutes": "supports"}
    return [(flip.get(s, s), c, q) for (s, c, q) in cfg]


def configs():
    for r in (1, 2, 3):
        yield from itertools.product(OPTS, repeat=r)
    rng = random.Random(11)
    for _ in range(15000):
        yield tuple(rng.choice(OPTS) for _ in range(rng.randint(4, 7)))


# ---------------------------------------------------------------- Theorem 1 (verdict rules)

def test_theorem1_characterisation_and_invariances_hold_on_every_configuration():
    seen = 0
    for cfg in configs():
        seen += 1
        v = aggregate(build(cfg)).verdict
        P, N = counted(cfg, "supports"), counted(cfg, "refutes")
        qp, qn = Q(P), Q(N)

        # (a) exact characterisation by the stated conditions
        if qp and qn:
            expected = "mixed"
        elif qp:
            expected = "mixed" if N else "supported"
        elif qn:
            expected = "mixed" if P else "refuted"
        else:
            expected = "insufficient"
        assert v == expected, (cfg, v, expected)
        assert (v == "insufficient") == (not qp and not qn)

        # (b) order invariance
        assert aggregate(build(tuple(reversed(cfg)))).verdict == v

        # (c) neutral and irrelevant sources never change the verdict
        assert aggregate(build(cfg + (("neutral", 0.95, False), ("irrelevant", 0.95, False)))).verdict == v

        # (d) symmetry under swapping supports and refutes
        swapped = aggregate(build(swap(cfg))).verdict
        assert swapped == {"supported": "refuted", "refuted": "supported"}.get(v, v)

        # (e) sources that fail the count conditions never change the verdict
        for extra in (("supports", 0.49, True), ("supports", 0.99, False), ("refutes", 0.49, True),
                      ("refutes", 0.99, False)):
            assert aggregate(build(cfg + (extra,))).verdict == v

        # (f) monotonicity of a supported verdict: only a counted refutation can change it, to mixed
        if v == "supported":
            for extra in OPTS:
                s, c, q = extra
                is_counted_refute = s == "refutes" and c >= CONFIDENCE_FLOOR and q
                after = aggregate(build(cfg + (extra,))).verdict
                assert after == ("mixed" if is_counted_refute else "supported"), (cfg, extra, after)

        # (g) verified-quote property: a verdict that asserts truth or falsity rests on a counted source
        if v in ("supported", "refuted", "mixed"):
            assert P or N
    assert seen > 27000


def test_theorem1_no_sources_and_low_confidence_corollary():
    assert aggregate([]).verdict == "no_sources"
    low = [("supports", 0.49, True), ("refutes", 0.3, True), ("supports", 0.1, True)]
    assert aggregate(build(low)).verdict == "insufficient"


def test_theorem1_shares_are_in_unit_interval():
    for cfg in configs():
        r = aggregate(build(cfg))
        assert -1e-12 <= r.support <= 1 + 1e-12 and -1e-12 <= r.conflict <= 1 + 1e-12
        assert r.support + r.conflict <= 1 + 1e-12


def test_worked_example_numbers():
    r = aggregate([src("supports", 0.95), src("supports", 0.90), src("neutral", 0.70), src("irrelevant", 0.90)])
    assert r.verdict == "supported"
    assert r.support == pytest.approx(1.85 / 2.55) and round(r.support, 3) == 0.725
    assert r.conflict == 0.0 and r.relevant == 3


# ---------------------------------------------------------------- Proposition 2 (entropy)

def softmax_entropy_u(s, tau):
    s = np.asarray(s, dtype=float)
    z = s / tau
    p = np.exp(z - z.max())
    p /= p.sum()
    h = -(p * np.log(p)).sum()
    return h / math.log(len(s)), p


def test_prop2_range_monotone_in_temperature_and_uniform_iff_equal():
    rng = np.random.default_rng(3)
    for _ in range(400):
        n = int(rng.integers(2, 12))
        s = rng.uniform(-1, 1, n)
        taus = np.sort(rng.uniform(0.02, 2.0, 6))
        us = [softmax_entropy_u(s, t)[0] for t in taus]
        assert all(0 <= u <= 1 + 1e-12 for u in us)
        assert all(b >= a - 1e-12 for a, b in zip(us, us[1:])), (s, taus, us)
    assert softmax_entropy_u([0.4] * 6, 0.1)[0] == pytest.approx(1.0)
    assert softmax_entropy_u([0.9, 0.1, 0.1], 0.1)[0] < 1.0


def test_prop2_lower_bound_on_near_equal_similarities():
    rng = np.random.default_rng(5)
    tested = 0
    for _ in range(2000):
        n = int(rng.integers(2, 15))
        tau = float(rng.uniform(0.05, 0.5))
        delta = float(rng.uniform(0.0, 0.2))
        s = rng.uniform(0.3, 0.3 + delta, n)
        spread = s.max() - s.min()
        u, _ = softmax_entropy_u(s, tau)
        bound = 1 - spread / (tau * math.log(n))
        assert u >= bound - 1e-12, (u, bound)
        tested += 1
    assert tested == 2000


def test_prop2_matches_the_implementation_up_to_its_epsilon():
    rng = np.random.default_rng(9)
    model = SimilarityDistributionEntropy(temperature=0.1)
    for _ in range(50):
        claim = rng.normal(size=(1, 16))
        ev = rng.normal(size=(int(rng.integers(2, 9)), 16))
        claim_u = claim / np.linalg.norm(claim, axis=1, keepdims=True)
        ev_u = ev / np.linalg.norm(ev, axis=1, keepdims=True)
        sims = (claim_u @ ev_u.T).ravel()
        assert model.compute_uncertainty(claim, ev) == pytest.approx(softmax_entropy_u(sims, 0.1)[0], abs=1e-6)


def test_paper_worked_example_for_entropy():
    u, p = softmax_entropy_u([0.62, 0.58, 0.31, 0.12], 0.1)
    assert np.round(p, 3).tolist() == [0.581, 0.389, 0.026, 0.004]
    assert round(float(-(p * np.log(p)).sum()), 3) == 0.800
    assert round(u, 3) == 0.577
    assert round((0.81 + u) / 2, 3) == 0.694


# ---------------------------------------------------------------- Proposition 3 (single-query degeneracy)

def test_prop3_density_reduces_to_knn_for_a_single_query():
    rng = np.random.default_rng(1)
    ref = rng.normal(size=(300, 16))
    est = DensityEstimator(n_neighbors=5)
    est.fit(ref)
    eps = 1e-9
    for _ in range(40):
        q = rng.normal(size=(1, 16)) * 1.5
        rho = float(est.compute_density_signal(q)[0])
        dist, _ = est.knn.kneighbors(q)
        dk = float(dist.mean())
        diff = (q - est.cov_estimator.location_)
        dm = float(np.sqrt(np.maximum((diff @ est.cov_estimator.precision_ * diff).sum(), 0)))
        assert abs(rho - (dk + 1) / 2) <= eps / (2 * dm) + 1e-12
        assert rho <= (dk + 1) / 2 + 1e-15
        # corollary: with cosine distance in [0, 2]... and d_k >= 0, retrieval confidence stays near or below 1/2
        assert max(0.0, 1.0 - rho) <= 0.5 + eps / (2 * dm) + 1e-12


def test_prop3_batch_normalisation_is_informative_for_batches():
    rng = np.random.default_rng(2)
    ref = rng.normal(size=(300, 16))
    est = DensityEstimator(n_neighbors=5)
    est.fit(ref)
    batch = rng.normal(size=(20, 16)) * np.linspace(0.5, 3, 20)[:, None]
    scores = est.compute_density_signal(batch)
    knn = est.knn.kneighbors(batch)[0].mean(axis=1)
    assert np.ptp(scores - knn / 2) > 0.05        # the Mahalanobis term varies across a batch


# ---------------------------------------------------------------- Proposition 4 (shrinkage)

def test_prop4_shrinkage_is_positive_definite_and_condition_bounded():
    rng = np.random.default_rng(4)
    from sklearn.covariance import LedoitWolf

    for _ in range(60):
        p = int(rng.integers(3, 25))
        n = int(rng.integers(2, 40))                  # includes n < p, where S is singular
        X = rng.normal(size=(n, p)) @ rng.normal(size=(p, p))
        lw = LedoitWolf().fit(X)
        S = np.cov(X, rowvar=False, bias=True)
        delta, mu = lw.shrinkage_, np.trace(S) / p
        sigma = (1 - delta) * S + delta * mu * np.eye(p)
        assert np.allclose(sigma, lw.covariance_, atol=1e-8)          # the formula in the paper is sklearn's
        eig = np.linalg.eigvalsh(sigma)
        if delta > 1e-9 and mu > 0:
            assert eig.min() >= delta * mu * (1 - 1e-9)
            cond = eig.max() / eig.min()
            assert cond <= ((1 - delta) * np.linalg.eigvalsh(S).max() + delta * mu) / (delta * mu) * (1 + 1e-9)
            assert cond <= 1 + (1 - delta) * p / delta + 1e-6


def test_worked_matrix_example():
    S = np.array([[2.0, 0.6], [0.6, 1.0]])
    delta, mu = 0.2, np.trace(S) / 2
    sigma = (1 - delta) * S + delta * mu * np.eye(2)
    assert np.allclose(sigma, [[1.9, 0.48], [0.48, 1.1]])
    assert round(float(np.linalg.det(sigma)), 4) == 1.8596
    v = np.array([1.0, 1.0])
    q = float(v @ np.linalg.inv(sigma) @ v)
    assert round(q, 4) == 1.0970 and round(math.sqrt(q), 3) == 1.047
    eig = np.linalg.eigvalsh(sigma)
    assert [round(float(x), 2) for x in eig] == [0.88, 2.12]
    assert round(float(eig.max() / eig.min()), 1) == 2.4
    assert eig.min() >= delta * mu and eig.max() / eig.min() <= 1 + (1 - delta) * 2 / delta   # Proposition 4
    # the 2 x 2 inverse printed in Appendix A.3
    assert np.allclose(np.linalg.inv(sigma) * 1.8596, [[1.1, -0.48], [-0.48, 1.9]], atol=1e-3)


# ---------------------------------------------------------------- matrix-derived numbers

EXPECTED = {
    "Pooled, OpenAlex": dict(acc=0.510, mf1=0.466, dec=0.667, nei_r=0.161, prec=[0.750, 0.484, 0.312], rec=[0.455, 0.861, 0.161]),
    "Pooled, Wikipedia": dict(acc=0.550, mf1=0.445, dec=0.797, nei_r=0.0, prec=[0.706, 0.484, 0.0], rec=[0.727, 0.861, 0.0]),
    "Stance, Wikipedia": dict(acc=0.530, mf1=0.528, dec=0.493, nei_r=0.613, prec=[0.500, 0.706, 0.514], rec=[0.667, 0.333, 0.613]),
}


@pytest.mark.parametrize("name", list(EXPECTED))
def test_table_numbers_follow_from_the_confusion_matrices(name):
    m = data.metrics(data.CONFUSION[name])
    e = EXPECTED[name]
    assert m["n"] == 100 and m["row_sums"] == [33, 36, 31]
    assert round(m["accuracy"], 3) == e["acc"]
    assert round(m["macro_f1"], 3) == e["mf1"]
    assert round(m["decisive_accuracy"], 3) == e["dec"]
    assert m["decisive_n"] == 69
    assert round(m["recall"][2], 3) == e["nei_r"]
    assert [round(x, 3) for x in m["precision"]] == e["prec"]
    assert [round(x, 3) for x in m["recall"]] == e["rec"]


def test_reported_confidence_intervals_follow_from_counts():
    pooled_oa = data.metrics(data.CONFUSION["Pooled, OpenAlex"])
    assert [round(x * 100, 1) for x in pooled_oa["accuracy_ci"]] == [41.3, 60.6]
    assert [round(x * 100, 1) for x in pooled_oa["decisive_ci"]] == [54.9, 76.6]
    wiki = data.metrics(data.CONFUSION["Pooled, Wikipedia"])
    assert [round(x * 100, 1) for x in wiki["accuracy_ci"]] == [45.2, 64.4]
    assert [round(x * 100, 1) for x in wiki["decisive_ci"]] == [68.8, 87.5]
    stance = data.metrics(data.CONFUSION["Stance, Wikipedia"])
    assert [round(x * 100, 1) for x in stance["accuracy_ci"]] == [43.3, 62.5]
    assert [round(x * 100, 1) for x in stance["decisive_ci"]] == [37.8, 60.8]


def _paired(run_a, run_b, decisive):
    import json
    root = ROOT / "results" / "verdict_eval"

    def load(run):
        lines = (root / run / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
        return {json.loads(x)["id"]: json.loads(x) for x in lines if x.strip()}

    a, b = load(run_a), load(run_b)
    ids = sorted(i for i in a if i in b and a[i]["predicted"] != "ERROR" and b[i]["predicted"] != "ERROR")
    if decisive:
        ids = [i for i in ids if a[i]["gold"] in ("SUPPORTS", "REFUTES")]
    ok = lambda r, i: r[i]["predicted"] == r[i]["gold"]  # noqa: E731
    only_a = sum(1 for i in ids if ok(a, i) and not ok(b, i))
    only_b = sum(1 for i in ids if ok(b, i) and not ok(a, i))
    n = only_a + only_b
    k = min(only_a, only_b)
    p = min(1.0, 2 * sum(math.comb(n, j) for j in range(k + 1)) / 2 ** n) if n else 1.0
    return len(ids), only_a, only_b, p


@pytest.mark.skipif(not (ROOT / "results" / "verdict_eval" / "stance_wiki_run1" / "predictions.jsonl").exists(),
                    reason="evaluation result files not present")
def test_paired_statistics_quoted_in_the_paper():
    n, a, b, p = _paired("pooled_wiki_run1", "baseline_pooled_run1", decisive=True)
    assert (n, a, b) == (69, 14, 5) and round(p, 3) == 0.064
    n, a, b, p = _paired("stance_wiki_run1", "pooled_wiki_run1", decisive=True)
    assert (n, a, b) == (69, 5, 26) and p < 0.001
    n, a, b, p = _paired("stance_wiki_run1", "pooled_wiki_run1", decisive=False)
    assert (n, a, b) == (100, 24, 26) and round(p, 2) == 0.89


def test_wilson_contains_phat_by_the_quadratic_argument():
    # Proposition 5: f(p) = (phat - p)^2 - z^2 p (1 - p) / n is convex, f(0), f(1) >= 0, f(phat) <= 0.
    z = 1.96
    for n in (5, 30, 100):
        for k in range(n + 1):
            ph = k / n
            f = lambda p: (ph - p) ** 2 - z * z * p * (1 - p) / n  # noqa: E731
            assert f(0) >= 0 and f(1) >= 0 and f(ph) <= 1e-15


def test_wilson_properties():
    for n in (1, 5, 30, 100):
        for k in range(n + 1):
            lo, hi = data.wilson(k, n)
            tol = 1e-12                      # at k = 0 or k = n an endpoint equals p-hat exactly
            assert 0 <= lo <= k / n + tol and k / n - tol <= hi <= 1
