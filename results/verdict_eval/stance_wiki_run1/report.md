# Verdict evaluation: stance_wiki

- Sample: N=100 (scored 100, errors 0), seed 42, model `openai/gpt-4o-mini`
- Accuracy: 53.0% (95% CI 43.3% to 62.5%)
- Macro-F1: 0.528
- Accuracy on SUPPORTS/REFUTES only: 49.3% (95% CI 37.8% to 60.8%)
- Coverage (at least one relevant source): 95.0%
- Mixed verdicts: 2.0%
- Median latency per claim: 7.2s
- Cost: $0.035

## Per class

| Gold | Precision | Recall | F1 | N |
|---|---|---|---|---|
| SUPPORTS | 50.0% | 66.7% | 0.571 | 33 |
| REFUTES | 70.6% | 33.3% | 0.453 | 36 |
| NOT ENOUGH INFO | 51.4% | 61.3% | 0.559 | 31 |

## Confusion (rows gold, columns predicted)

| Gold | SUPPORTS | REFUTES | NOT ENOUGH INFO | MIXED |
|---|---|---|---|---|
| SUPPORTS | 22 | 2 | 8 | 1 |
| REFUTES | 13 | 12 | 10 | 1 |
| NOT ENOUGH INFO | 9 | 3 | 19 | 0 |

## Caveats

- FEVER claims are Wikipedia-derived and the language model may have seen them; compare configurations relatively.
- NOT ENOUGH INFO is not the same as no source found; a source-poor retriever lowers apparent NEI recall differently.
- Small N gives wide intervals. Differences inside the intervals are not evidence of improvement.
