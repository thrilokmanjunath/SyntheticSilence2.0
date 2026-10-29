# Verdict evaluation: pooled_wiki

- Sample: N=100 (scored 100, errors 0), seed 42, model `openai/gpt-4o-mini`
- Accuracy: 55.0% (95% CI 45.2% to 64.4%)
- Macro-F1: 0.445
- Accuracy on SUPPORTS/REFUTES only: 79.7% (95% CI 68.8% to 87.5%)
- Coverage (at least one relevant source): 100.0%
- Mixed verdicts: 0.0%
- Median latency per claim: 6.0s
- Cost: $0.031

## Per class

| Gold | Precision | Recall | F1 | N |
|---|---|---|---|---|
| SUPPORTS | 70.6% | 72.7% | 0.716 | 33 |
| REFUTES | 48.4% | 86.1% | 0.620 | 36 |
| NOT ENOUGH INFO | 0.0% | 0.0% | 0.000 | 31 |

## Confusion (rows gold, columns predicted)

| Gold | SUPPORTS | REFUTES | NOT ENOUGH INFO | MIXED |
|---|---|---|---|---|
| SUPPORTS | 24 | 8 | 1 | 0 |
| REFUTES | 4 | 31 | 1 | 0 |
| NOT ENOUGH INFO | 6 | 25 | 0 | 0 |

## Caveats

- FEVER claims are Wikipedia-derived and the language model may have seen them; compare configurations relatively.
- NOT ENOUGH INFO is not the same as no source found; a source-poor retriever lowers apparent NEI recall differently.
- Small N gives wide intervals. Differences inside the intervals are not evidence of improvement.
