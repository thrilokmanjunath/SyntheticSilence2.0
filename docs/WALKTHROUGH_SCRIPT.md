# Synthetic Silence 2.0: 2-Minute Video Walkthrough Script & Recording Guide

**Target Duration:** 2 minutes (120 seconds)  
**Presenter:** Thrilok Manjunath  
**Focus:** Scientific problem, pipeline architecture, frozen benchmark reproduction, empirical inversion finding, and research limitations.

---

## 🎬 Storyboard & Timing Breakdown

### [00:00 – 00:20] Segment 1: The Research Problem & Motivation
- **Visual:** Display `streamlit_app.py` UI or Title Slide of `Synthetic_Silence_Final_Presentation.pptx`.
- **Narration:**
  > "Large language models frequently generate fluent, plausible claims that are completely ungrounded in fact. Recent literature hypothesized that representation-space density—measuring how closely a claim clusters near verified knowledge embeddings—could detect evidence insufficiency. In Synthetic Silence 2.0, we subjected this hypothesis to rigorous empirical stress testing across domain shifts to determine whether claim density is truly a reliable safety signal."

### [00:20 – 00:45] Segment 2: Pipeline Architecture & Frozen Benchmarks
- **Visual:** Terminal executing `python scripts/reproduce_benchmark.py` showing frozen manifest hashes loading.
- **Narration:**
  > "Our architecture decouples into two regimes: first, an offline experimental testbed evaluating frozen claim manifolds from FEVER and real-world AVeriTeC fact-checking archives. Second, a deterministic verification pipeline with split-conformal prediction sets and verbatim quote matching. Everything in this repository runs offline with cryptographically frozen manifests, ensuring complete zero-leakage reproducibility without relying on external API calls."

### [00:45 – 01:20] Segment 3: The Empirical Inversion Finding (AUROC 0.5463 ➔ 0.2754)
- **Visual:** Highlight the Master Results Table in `README.md` and the terminal table output.
- **Narration:**
  > "Here is our core empirical discovery: On synthetic, Wikipedia-templated FEVER claims, kNN density exhibited a modest discriminative signal with an AUROC of 0.5463. But when evaluated on real-world AVeriTeC claims, the signal suffered a catastrophic inversion: the AUROC dropped to 0.2754 for insufficient evidence claims. 
  > 
  > Why? Because insufficient real-world claims often mirror formal encyclopedic phrasing, clustering closer to reference manifolds than legitimately supported claims. Furthermore, in cross-manifold tests, discrimination collapsed to random chance at 0.50. This definitively proves that representation density is an artifact of stylistic construction, not epistemic truth."

### [01:20 – 01:45] Segment 4: Interactive Verification Demonstration
- **Visual:** Switch to `streamlit_app.py`, load "Case 2: AVeriTeC Insufficient Evidence" preset, show the amber verdict and conformal prediction set.
- **Narration:**
  > "To solve this, our interactive platform pivots to grounded verification. As seen here on an ambiguous meteorite claim, rather than trusting density, the engine verifies verbatim source quotes, applies deterministic stance rules, and produces a mathematically bounded conformal prediction set that guarantees coverage under user-specified error tolerances."

### [01:45 – 02:00] Segment 5: Limitations & Conclusion
- **Visual:** Display the Limitations section in `README.md` and the GitHub repository link.
- **Narration:**
  > "Our work carries explicit limitations: conformal bounds depend on exchangeability, which can be violated under acute temporal drift, and offline evaluation assumes high-recall retrieval. However, by establishing this empirical failure mode, Synthetic Silence 2.0 steers the field toward honest, deterministic verification. The entire benchmark can be reproduced with a single command. Thank you."

---

## 🎥 Recording Instructions
1. Run the local Streamlit application: `streamlit run streamlit_app.py --server.port 8501`.
2. Open terminal side-by-side with browser window (1920x1080 resolution).
3. Use QuickTime Player (`Cmd + Shift + 5`) or OBS Studio to capture full screen at 60 FPS.
4. Execute `python scripts/reproduce_benchmark.py` in the terminal during Segment 2.
5. Export MP4 video to `docs/walkthrough_demo.mp4`.
