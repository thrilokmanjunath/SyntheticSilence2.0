# Verdict evaluation: pooled_wiki

- Sample: N=150 (scored 68, errors 82), seed 43, model `openai/gpt-4o-mini`
- Accuracy: 54.4% (95% CI 42.7% to 65.7%)
- Macro-F1: 0.484
- Accuracy on SUPPORTS/REFUTES only: 83.3% (95% CI 69.4% to 91.7%)
- Coverage (at least one relevant source): 100.0%
- Mixed verdicts: 0.0%
- Median latency per claim: 5.5s
- Cost: $0.022

## Per class

| Gold | Precision | Recall | F1 | N |
|---|---|---|---|---|
| SUPPORTS | 66.7% | 90.9% | 0.769 | 22 |
| REFUTES | 42.9% | 75.0% | 0.545 | 20 |
| NOT ENOUGH INFO | 66.7% | 7.7% | 0.138 | 26 |

## Confusion (rows gold, columns predicted)

| Gold | SUPPORTS | REFUTES | NOT ENOUGH INFO | MIXED |
|---|---|---|---|---|
| SUPPORTS | 20 | 1 | 1 | 0 |
| REFUTES | 5 | 15 | 0 | 0 |
| NOT ENOUGH INFO | 5 | 19 | 2 | 0 |

## Caveats

- FEVER claims are Wikipedia-derived and the language model may have seen them; compare configurations relatively.
- NOT ENOUGH INFO is not the same as no source found; a source-poor retriever lowers apparent NEI recall differently.
- Small N gives wide intervals. Differences inside the intervals are not evidence of improvement.
