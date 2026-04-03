# Priva-Fed Documentation Index

This directory contains the technical documentation suite for the Priva-Fed framework, summarizing the journey from synthetic dataset generation to a hardened, privacy-preserving federated retrieval system.

## 📄 Core Documentation

### 1. [Benchmark Results & Walkthrough](benchmark_results.md)
**Essential Reading.** Contains the absolute final v4 empirical results:
- **Defense Matrix**: Verification of cryptographic and noise-based defenses.
- **Utility-Privacy Trade-off**: The definitive results table.
- **Recommended Operating Point**: Rationale for the `combined ns=2.0` configuration.

### 2. [Privacy Design & Threat Model](privacy_analysis.md)
Theoretical justification and adversarial analysis:
- Details on **VS-ADP** and **HE-Lite**.
- Categorization of attackers (Query-intercept vs. Score-intercept).
- Epsilon framing and RDP mechanism explanation.

### 3. [Metrics Guide](metrics_explained.md)
Glossary and mathematical definitions of performance indicators:
- **Utility**: R@1, MRR, NDCG, Semantic Drift.
- **Privacy**: ASR, MIA, ScoreInf, Reconstruction CosSim.

### 4. [Baseline Analysis](baseline_analysis.md)
Historical context of how the 86.0% R@1 plaintext "Gold Standard" was achieved through Hybrid RRF and Cross-Encoder re-ranking.

### 5. [Project Status Report](project_status_report.md)
High-level summary of phase completions, key findings, and future work.

---

## 🏗️ Technical Implementation
- **Mechanism Implementation**: See `src/privacy.py`.
- **Adversarial Simulation**: See `src/attack.py`.
- **Protocol Orchestration**: See `src/hub.py` and `src/local_retrieval.py`.
