# IEEE draft

`content.py` holds the text, equations, tables and references once. `build_paper.py` turns it into:

- `out/SyntheticSilence_IEEE_Draft.docx`: two-column Word document in IEEE conference layout
- `out/SyntheticSilence_IEEE_Draft.tex`: IEEEtran source (`pdflatex` twice; not compiled by the script)
- `out/figs/pipeline.png`: Figure 1

```bash
python paper/build_paper.py                      # needs python-docx and matplotlib
.venv/Scripts/python -m pytest paper/test_mathtext.py
```

## Journal draft (TACL format, theorems with proofs, matrices)

```bash
python paper/journal/build_journal.py                  # writes out/SyntheticSilence_Journal_Draft.{docx,tex}
.venv/Scripts/python -m pytest paper                   # property checks, matrix numbers, content checks
```

- `journal/content_journal.py`: the text, 5 propositions with proofs, matrices and tables
- `journal/data.py`: the confusion matrices and every metric derived from them
- `journal/refs_journal.py`: verified references in TACL style; `journal/FORMAT_NOTES.md`: sources and open items
- `test_propositions.py` checks each proposition against the deployed code (the real verdict function,
  density estimator, entropy module, scikit-learn's Ledoit-Wolf) and each table number against its matrix
- The `.tex` follows the official template; put `tacl2021v1.sty` from https://transacl.org/tacl-submission-templates/
  next to it. It has not been compiled here.

## Table III (cross-model audit) is empty until the audit has run

```bash
python scripts/eval_llm_responses.py --dry-run               # plan and cost estimate, calls nothing
python scripts/eval_llm_responses.py --budget-usd 3 --run-id audit1
python paper/build_paper.py                                  # picks up the newest results/llm_eval/*/summary.json
```

The abstract, Section V-C and the conclusion mention that the audit has not been run. When it has, update
those sentences by hand; the script does not rewrite prose.

## Before submitting

- Replace the author and affiliation placeholders and the acknowledgment.
- Check every reference against its source; the entries were written from memory.
- Check the numbers in Tables I and II against `docs/VERDICT_EVALUATION.md` and `results/verdict_eval/`.
