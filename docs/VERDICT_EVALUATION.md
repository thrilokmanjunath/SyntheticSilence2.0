# Verdict evaluation (extension backend)

What this measures: how often the **user-facing verdict** of the extension backend agrees with FEVER gold
labels. It is separate from the paper's E0/E1 experiments, which evaluate the density signal and are untouched.

Harness: `backend/experiments/verdict_eval.py`, CLI `scripts/eval_verdict.py`. Raw per-claim predictions and
reports are in `results/verdict_eval/<run_id>/`.

## Setup

- Claims: `data/raw/fever/paper_dev.jsonl`, balanced SUPPORTS / REFUTES / NOT ENOUGH INFO, deduplicated by id.
- Label mapping: supported -> SUPPORTS, refuted -> REFUTES, insufficient / no_sources -> NOT ENOUGH INFO,
  mixed -> reported separately (counts as wrong).
- LLM: `openai/gpt-4o-mini` at temperature 0 via OpenRouter. Claims are given (no extraction step).
- Variants:
  - `pooled`: v1 behaviour. One NLI score over all pooled sources, display bins (conflict >= 0.5 -> refuted, support >= 0.6 -> supported).
  - `stance`: one LLM call returns a stance per source with a verbatim quote; deterministic aggregation (`backend/app/services/algo/stance.py`).
  - Retrievers: `openalex` (scholarly) or `wikipedia` (encyclopedic).

## Results

### Run 1: baseline, paired subset (seed 42)

The baseline `pooled` + OpenAlex run scored 100 of 150 claims. The other 50 failed because the anonymous OpenAlex
daily budget (about 100 searches per IP) was used up, and are excluded. The two Wikipedia variants were run on
exactly those 100 claims.

| Variant | Accuracy (95% CI) | Macro-F1 | SUPPORTS/REFUTES only (95% CI) | NEI recall | Coverage |
|---|---|---|---|---|---|
| pooled + OpenAlex (baseline) | 51.0% (41.3 to 60.6) | 0.466 | 66.7% (54.9 to 76.6) | 16% | 97% |
| pooled + Wikipedia | 55.0% (45.2 to 64.4) | 0.445 | 79.7% (68.8 to 87.5) | 0% | 100% |
| stance + Wikipedia, **first version** | 53.0% (43.3 to 62.5) | 0.528 | 49.3% (37.8 to 60.8) | 61% | 95% |

Reading it:

- Wikipedia helps on SUPPORTS/REFUTES claims (66.7% -> 79.7%) because FEVER is itself Wikipedia-derived.
- Pooled NLI never says "not enough info": it called 25 of 31 NEI claims REFUTES. A pooled score cannot tell
  "the sources don't mention it" from "the sources contradict it".
- The first stance version fixed that (NEI recall 0% -> 61%) but lost SUPPORTS/REFUTES accuracy: 13 of 36
  refuted claims were called SUPPORTS.

### Diagnosis of the stance regression

Inspecting those 13 cases found two causes, both mine:

1. Stance was judged against the LLM-**normalised** claim, which dropped the detail that made the claim false
   ("The Monster is a restaurant by Eminem" became "The Monster is a restaurant"; "television show" became "show").
2. The prompt accepted near-misses as support (1945 for 1946; a television series for a radio station).

Fixes: stance and ranking now use the claim exactly as written, and the prompt requires every specific detail to
be confirmed (a different year or category is a conflict, not support). Normalisation is used only to build
search queries. A regression test pins the first fix.

### Run 2: fixed stance, fresh sample (seed 43) - INCOMPLETE

Re-evaluation on a fresh sample was cut off when the OpenRouter account ran out of credit (HTTP 402) after
68 (pooled) and 27 (stance) claims. These counts are far too small to compare, so **no conclusion is drawn**.
The incomplete numbers are kept in `results/verdict_eval/*_s43` for transparency only.

## Decision

The fixed stance mode is **not yet shown to beat pooled**, so the default stays `SS_VERDICT_MODE=pooled`
(v1 behaviour, now with Wikipedia added as a retriever). Stance mode is opt-in and is what enables per-source
stance chips and highlighted quotes in the UI.

To finish the comparison once the LLM account has credit:

```bash
python scripts/eval_verdict.py --variant pooled_wiki  --n 150 --seed 43 --run-id pooled_wiki_s43_full
python scripts/eval_verdict.py --variant stance_wiki  --n 150 --seed 43 --run-id stance_wiki_s43_full
```

Flip the default to `stance` only if its macro-F1 and SUPPORTS/REFUTES accuracy are not worse than pooled
beyond the confidence intervals.

## Caveats

- FEVER claims are Wikipedia-derived and the language model may have seen them; compare variants relatively,
  not as absolute accuracy.
- NOT ENOUGH INFO is not the same as "no source found".
- N=100 to 150 gives wide intervals (about +/-10 points). Differences inside them are not evidence.
- The density/entropy "gap score" is not part of the verdict and is not evaluated here; the paper's finding
  that it does not generalise stands.

## Operational findings

- OpenAlex without an API key shares a tiny daily budget per IP. One extension check can use several searches.
  Set `OPENALEX_API_KEY` (free) or rely on Wikipedia. The service stops calling OpenAlex for the rest of the
  budget window and reports a budget error instead of silently returning no sources.
- A retrieval or LLM outage is always an explicit error (per claim in the stream), never an empty source list.
