# Priva-Fed Framework (Revised & Hardened)

## Project Definition
Priva-Fed is a domain-agnostic benchmarking framework for privacy-preserving federated semantic retrieval, designed to quantitatively measure the trade-off between latency, privacy strength, and semantic utility in real-world Retrieval-Augmented Generation (RAG) systems operating over unstructured text.

**Core Philosophy:** Finance is a demonstration domain, not the limitation.

## 1. The Goal
To develop Priva-Fed, a federated secure retrieval framework that enables multiple organizations to collaboratively query unstructured narrative intelligence (e.g., fraud reports, legal case notes, clinical summaries, incident logs) without sharing raw text or embeddings.

Crucially, Priva-Fed is not a new privacy mechanism, but a comparative benchmarking system that empirically quantifies the trade-offs between:
- **Vector-Space Approximate Differential Privacy (VS-ADP)** → Low latency, tunable semantic degradation
- **Homomorphic Encryption (HE-Lite)** → High privacy guarantees, high computational cost

This framework directly addresses the Latency vs. Semantic Utility dilemma that blocks real-time deployment of privacy-preserving RAG systems.

## 2. Problem Statement
**The Unstructured Privacy Paradox: Benchmarking Latency vs. Semantic Utility in Federated Semantic Retrieval**

### 2.1 The Data Silos Problem (Domain-Agnostic)
Across high-stakes domains—finance, law, healthcare, cybersecurity, intelligence analysis—organizations accumulate massive volumes of unstructured narratives (Investigator notes, Case summaries, Incident reports, etc.). These texts encode latent institutional knowledge but cannot be centrally aggregated due to privacy regulations and competitive sensitivity. Unlike structured numerical data, textual intelligence cannot be trivially anonymized without destroying meaning.

### 2.2 The Technical Dilemma
- **Homomorphic Encryption (HE)**: Strong guarantees but prohibitive latency for similarity search.
- **Differential Privacy (DP)**: Fast but naive noise injection distorts semantic geometry and degrades retrieval recall.

### 2.3 The Research Gap
There is no standard framework to systematically measure privacy–latency–utility trade-offs for unstructured semantic retrieval. Priva-Fed fills this gap.

## 3. Architecture
Priva-Fed follows a Hub-and-Spoke architecture with pluggable privacy adapters.

### 3.1 Core Components
- **The Hub (Orchestrator)**: Lightweight Python service. Broadcasts query embeddings, aggregates privacy-safe responses, re-ranks. never accesses raw documents.
- **The Nodes (Spokes)**: Independent organizations. Each has a local FAISS index (plaintext) and a PrivacyAdapter middleware.
- **The PrivacyAdapter**: Modular interception layer. Modes: `vs_adp` query/response noise, `he_lite` partial encryption.
- **The Comparator**: Benchmarking logger for latency, recall@k, semantic drift, bandwidth.

## 4. Privacy Modes
### 4.1 VS-ADP (Vector-Space Approximate Differential Privacy)
- **Mechanism**: Add calibrated noise (Laplace/Gaussian) to embedding vectors post-retrieval.
- **Purpose**: Enable fast, tunable privacy; quantify semantic degradation.

### 4.2 HE-Lite (Homomorphic Encryption)
- **Design Choice**: Local similarity search remains plaintext. Selected similarity scores are encrypted. HE applied to aggregation/re-ranking.
- **Why**: Captures cryptographic overhead without unrealistic full-retrieval latency claims.

## 5. Execution Plan
- **Phase 1: Synthetic Narrative Generation**: Generate realistic unstructured text (Narrative-Synth).
- **Phase 2: Local Semantic Retrieval**: Establish upper-bound baseline (Recall@k without privacy).
- **Phase 3: Privacy Engine Integration**: Implement `vs_adp` and `he_lite` adapters.
- **Phase 4: Benchmarking & Evaluation**: Run experiments, generate `results.csv` and plots.

## 6. Contribution Statement
Priva-Fed contributes:
1. A domain-agnostic federated semantic retrieval framework.
2. A benchmarking methodology for privacy vs utility in unstructured text.
3. An empirical comparison of VS-ADP vs HE-Lite.
4. Reproducible synthetic narrative generation for private domains.

## 7. Documentation & Results
Detailed analysis, benchmark results, and metric explanations can be found in the [docs/](docs/README_PRIVACY.md) directory:

- 📄 **[Benchmark Results & Walkthrough](docs/benchmark_results.md)**: Final v4 benchmark results and analysis.
- 📊 **[Metrics Explained](docs/metrics_explained.md)**: Definitions of R@1, ASR, ScoreInf, etc.
- 🛡️ **[Privacy Analysis](docs/privacy_analysis.md)**: Threat model and theoretical justification.
- 📉 **[Baseline Analysis](docs/baseline_analysis.md)**: Initial performance baselines.
