# Priva-Fed Privacy Documentation

This directory contains the detailed analysis, benchmarking results, and metric explanations for the Priva-Fed framework.

## 📄 Key Documents

### 1. [Benchmark Results & Walkthrough](benchmark_results.md)
**Start here.** A comprehensive walkthrough of the final v4 benchmark.
- **Defense Matrix**: Shows how the combined pipeline defends against both query and score attacks.
- **Results Table**: Full privacy-utility trade-off data.
- **Issues Fixed**: Summary of the 12 critical fixes implemented.

### 2. [Metrics Explained](metrics_explained.md)
 detailed definitions of all metrics used in the paper/project:
- **Utility**: Recall@k, MRR, NDCG, Semantic Drift.
- **Privacy**: Attack Success Rate (ASR), Score Inference (ScoreInf), Membership Inference (MIA), etc.
- **Why it matters**: Justification for why each metric was chosen.

### 3. [Privacy Analysis](privacy_analysis.md)
Initial theoretical analysis of the privacy requirements and threat model.
- Analyzes GDPR compliance needs.
- Defines the local vs. global adversary model.
- Justifies the choice of VS-ADP and HE-Lite.

### 4. [Baseline Analysis](baseline_analysis.md)
Analysis of the initial system performance before privacy mechanisms were added.
- Establishes the "gold standard" utility baseline.

## 📂 Source Code References
- `src/privacy.py`: Implementation of VS-ADP and HE-Lite.
- `src/attack.py`: The attack suite (Known-Template, MIA, Reconstruction).
- `src/benchmark_full.py`: The main benchmarking script.
