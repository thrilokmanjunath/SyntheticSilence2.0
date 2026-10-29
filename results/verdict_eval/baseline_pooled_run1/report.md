# Verdict evaluation: pooled

- Sample: N=150 (scored 100, errors 50), seed 42, model `openai/gpt-4o-mini`
- Accuracy: 51.0% (95% CI 41.3% to 60.6%)
- Macro-F1: 0.466
- Accuracy on SUPPORTS/REFUTES only: 66.7% (95% CI 54.9% to 76.6%)
- Coverage (at least one relevant source): 97.0%
- Mixed verdicts: 0.0%
- Median latency per claim: 5.7s
- Cost: $0.044

## Per class

| Gold | Precision | Recall | F1 | N |
|---|---|---|---|---|
| SUPPORTS | 75.0% | 45.5% | 0.566 | 33 |
| REFUTES | 48.4% | 86.1% | 0.620 | 36 |
| NOT ENOUGH INFO | 31.2% | 16.1% | 0.213 | 31 |

## Confusion (rows gold, columns predicted)

| Gold | SUPPORTS | REFUTES | NOT ENOUGH INFO | MIXED |
|---|---|---|---|---|
| SUPPORTS | 15 | 9 | 9 | 0 |
| REFUTES | 3 | 31 | 2 | 0 |
| NOT ENOUGH INFO | 2 | 24 | 5 | 0 |

## Caveats

- FEVER claims are Wikipedia-derived and the language model may have seen them; compare configurations relatively.
- NOT ENOUGH INFO is not the same as no source found; a source-poor retriever lowers apparent NEI recall differently.
- Small N gives wide intervals. Differences inside the intervals are not evidence of improvement.
