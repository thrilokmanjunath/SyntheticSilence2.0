# Changelog

All notable changes to the Synthetic Silence research project are documented here.

## [2.0.0] - 2026-10-29

### Scientific Research & Evaluation
- **E0 (FEVER Baseline):** Evaluated representation-space density ($B_3$) on 18,631 FEVER instances ($\text{AUROC} = 0.5463$, 95% CI $[0.5366, 0.5564]$).
- **E1 (AVeriTeC Stress Test):** Discovered severe signal inversion on 500 naturalistic test claims ($\text{AUROC} = 0.3545$ overall; $\text{AUROC} = 0.2754$ on `retrieved_insufficient`).
- **F1 (Cross-Manifold Diagnostic):** Proved cross-domain topological metrics collapse to random chance ($\text{AUROC} \approx 0.50$).
- **F2 (Matched Negative Controls):** Implemented 1:1 Mahalanobis distance matching (29 pairs, SMD < 0.02) on length and lexical diversity; proved signal inversion persists ($\text{AUROC} = 0.3353$).
- **Frozen Records:** Established immutable research records in `results/FINAL_RESEARCH_FREEZE/` and `results/FINAL_PAPER_PACKAGE/`.

### Engineering & System Implementation
- **Evidence-Grounded Engine:** Implemented real-time retrieval with Wikipedia and OpenAlex backends, including budget exhaustion and error isolation.
- **Deterministic 5-Rule Verdict Pipeline:** Added stance classification with verbatim quote verification (`Supported`, `Refuted`, `Conflicting`, `Insufficient`, `Stale`).
- **Conformal Calibration:** Added split-conformal prediction interface defaulting to `NOT_CALIBRATED` to avoid false certainty.
- **Manifest V3 Chrome Extension:** Built TypeScript extension for Chrome with popup, sidepanel, page highlighter, and SSE streaming.
- **Academic Manuscripts:** Built IEEE Conference paper generator and TACL Journal manuscript with 5 mathematical propositions and empirical verification tests.

### Cross-Platform Engineering & Publication Release
- **Cross-Platform Compatibility:** Fixed Python detection across Windows, macOS (Apple Silicon), and Linux in extension build tooling.
- **Repository Hygiene:** Untracked legacy compiled `.pyc` files, cleaned up unzipped PowerPoint build scrap, added `.gitignore`, `.gitattributes`, `.editorconfig`, `pyproject.toml`, `requirements.txt`, and GitHub Actions CI.
- **Test Suite:** 195 automated tests across backend (117), paper (34), and Chrome extension (44).

## [1.0.0] - 2026-08-11
- Initial exploration of representation density and topological data analysis on LLM hallucination.
