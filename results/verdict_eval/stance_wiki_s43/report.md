# Verdict evaluation: stance_wiki

- Sample: N=150 (scored 27, errors 123), seed 43, model `openai/gpt-4o-mini`
- Accuracy: 55.6% (95% CI 37.3% to 72.4%)
- Macro-F1: 0.554
- Accuracy on SUPPORTS/REFUTES only: 57.9% (95% CI 36.3% to 76.9%)
- Coverage (at least one relevant source): 92.6%
- Mixed verdicts: 0.0%
- Median latency per claim: 7.3s
- Cost: $0.011

## Per class

| Gold | Precision | Recall | F1 | N |
|---|---|---|---|---|
| SUPPORTS | 57.1% | 61.5% | 0.593 | 13 |
| REFUTES | 75.0% | 50.0% | 0.600 | 6 |
| NOT ENOUGH INFO | 44.4% | 50.0% | 0.471 | 8 |

## Confusion (rows gold, columns predicted)

| Gold | SUPPORTS | REFUTES | NOT ENOUGH INFO | MIXED |
|---|---|---|---|---|
| SUPPORTS | 8 | 1 | 4 | 0 |
| REFUTES | 2 | 3 | 1 | 0 |
| NOT ENOUGH INFO | 4 | 0 | 4 | 0 |

## Caveats

- FEVER claims are Wikipedia-derived and the language model may have seen them; compare configurations relatively.
- NOT ENOUGH INFO is not the same as no source found; a source-poor retriever lowers apparent NEI recall differently.
- Small N gives wide intervals. Differences inside the intervals are not evidence of improvement.
