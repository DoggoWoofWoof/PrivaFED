# Priva-Fed: Federated Privacy-Utility Benchmarking for Unstructured Retrieval

Welcome to the **Priva-Fed** framework. This repository provides a domain-agnostic benchmarking system designed to quantify the trade-offs between retrieval performance (utility), computational cost (latency/bandwidth), and privacy strength in federated Search-Augmented Generation (RAG) environments.

## 🚀 Final Project Achievement
The benchmarking phase is **Completed & Verified**. High-utility privacy-preserving retrieval is possible:
- **Combined Mode (ns=2.0)**: Fully protects score-side channels (MIA/ScoreInf/Recon) while reducing single-query fingerprint ASR.
- **Utility Preservation**: Achieves **R@1 = 0.940** under encrypted scoring, compared to a **0.860** plaintext baseline.
- **Paper Ready**: Finalized empirical tables and adversarial assessments are documented in `docs/benchmark_results.md`.

---

## 🏗️ Architecture
Priva-Fed uses a **Hub-and-Spoke** topology to simulate real-world data silos:
- **The Hub (Client)**: Orchestrates the multi-pass retrieval protocol without ever accessing raw text.
- **Local Nodes (Orgs)**: Maintain local FAISS/BM25 indices and apply organization-specific privacy overrides.
- **Privacy Adapters**: Modular layers implementing **VS-ADP** (Vector-Space Noise) and **HE-Lite** (Encrypted Scores).

---

## 🛡️ Privacy Mechanisms
1. **VS-ADP (Vector-Space Approximate Differential Privacy)**:
   - Adds dimensionality-aware Gaussian noise to query embeddings.
   - Reduces Query Fingerprinting Attack Success Rate (ASR) into the **0.676-0.720** range at high noise levels.
2. **HE-Lite (Homomorphic Encryption)**:
   - Uses CKKS (via TenSEAL) to encrypt similarity scores in transit.
   - Blocks Membership Inference (MIA) and Embedding Reconstruction attacks (Accuracy dropped to **0.500/0.000**).
3. **LSH (Locality Sensitive Hashing)**:
   - Maps embeddings to 64-bit binary SimHash signatures as a fast, non-cryptographic baseline for score protection.
4. **P2P Masking (Secure Aggregation)**:
   - Ensures the Hub only sees the global score sum, not individual node contributions.

---

## 📈 Key Findings
- **The Unstructured Privacy Paradox**: Protecting relevance scores cryptographically (HE) introduces an approximately **2,964x bandwidth overhead**, identifying a key practical bottleneck.
- **Empirical Resistance**: High-noise regimes ($\epsilon \approx 20,000$) are framed as **empirical adaptive resistance** via Hub rate-limiting, rather than formal DP guarantees.

---

## 📂 Documentation Index
- 📄 **[Benchmark Results](docs/benchmark_results.md)**: Final verified metrics and analysis.
- 📊 **[Metrics Explained](docs/metrics_explained.md)**: IR and Privacy metric definitions.
- 🛡️ **[Privacy Analysis](docs/privacy_analysis.md)**: Threat model and theoretical justification.
- 📋 **[Project Status](docs/project_status_report.md)**: Final synthesis of achievements.

---

## 🛠️ Usage
1. **Setup**: `pip install sentence-transformers faiss-cpu tenseal rank_bm25`
2. **Generate Data**: `python src/narrative_synth.py`
3. **Run Benchmark**: `python src/benchmark_full.py`
4. **View Results**: Check `results/results.csv` and the `docs/` folder.

---
*Created for the Advanced Agentic Coding workshop as a study of decentralized semantic retrieval.*
