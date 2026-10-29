# Contributing to Synthetic Silence

We welcome contributions, scientific audits, issue reports, and replication studies.

## Scientific Integrity Principles
Synthetic Silence is an empirical computational research project. Any contributions affecting evaluation protocols, baselines, or datasets must adhere to these core rules:
1. **Never mutate frozen evaluation artifacts:** Historical records (`results/FINAL_RESEARCH_FREEZE/`, `results/FINAL_PAPER_PACKAGE/`) represent historical findings and must remain immutable.
2. **Quarantine against data leakage:** Evaluation sets (e.g. `averitec_E1_TEST.jsonl`) must never be used for fitting manifolds, calibrating thresholds, or feature engineering.
3. **Transparent uncertainty:** If a metric or model is not calibrated on target domain data, it must report `NOT_CALIBRATED` rather than arbitrary probability values.

## Development Workflow

### Python Backend & Research Experiments
1. Create and activate a virtual environment:
   ```bash
   # macOS / Linux
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt

   # Windows PowerShell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```
2. Configure environment:
   ```bash
   cp backend/.env.example backend/.env
   # Add your OPENROUTER_API_KEY (and optional OPENALEX_API_KEY)
   ```
3. Run tests before submitting changes:
   ```bash
   pytest -q backend/tests
   pytest -q paper/test_*.py
   ```

### Chrome Extension
1. Install Node.js 20+:
   ```bash
   cd extension
   npm install
   npm test
   ```
2. Build the extension:
   ```bash
   npm run build
   ```
3. Load unpacked extension via `chrome://extensions`.
