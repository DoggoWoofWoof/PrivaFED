# Project Status Report: Priva-Fed

**Project Title:** Priva-Fed: Benchmarking Privacy-Utility Trade-offs in Federated Semantic Retrieval

## 1. Project Overview & Current Status
We have developed a domain-agnostic federated semantic retrieval system that enables organizations to collaboratively query unstructured narratives without exposing sensitive data. The project has successfully completed the **adversarial evaluation and benchmarking phase**.

### Phase 1: Synthetic Narrative Generation (Completed)
- **Outcome:** A robust pipeline generating realistic, template-based documents with embedded PII. Generated 300 documents across 3 organizations.

### Phase 2: Local Semantic Retrieval Baseline (Completed)
- **Implementation:** FAISS index with `all-MiniLM-L6-v2` embeddings. Established the "gold standard" utility target.

### Phase 3: Privacy Engine Implementation (Completed)
- **VS-ADP**: Dimensionality-aware Gaussian noise injection.
- **HE-Lite**: Secure score aggregation using TenSEAL (CKKS).
- **LSH**: 64-bit SimHash adapter implemented for comparison.
- **Combined**: Hybrid pipeline integrating both HE and VS-ADP.

### Phase 4: Adversarial Evaluation & Benchmarking (Completed)
- **Attack Suite**: Implemented KnownTemplate, MultiQuery, Membership Inference (MIA), Score Inference, and Embedding Reconstruction attacks.
- **Evaluation Metrics**: Comprehensive evaluation measuring specific performance (Recall, MRR, NDCG, Rank Correlation) and defense outcomes (ASR, MIA Accuracy, Recon CosSim, and geometric divergence via Recon Error).
- **Defense Matrix**: Successfully mapped the resilience of all privacy modes across 5 different attack vectors.
- **Outcome**: Verified that HE-Lite/Combined fully protect score-side channels (MIA/ScoreInf/Recon), while VS-ADP-family modes reduce (but do not eliminate) query fingerprinting success.

## 2. Key Empirical Findings (Verified Final)
- **Combined Protection**: The combined pipeline (ns=2.0) maintains high utility (R@1=0.940) while fully blocking score-side attacks (MIA=0.500, ScoreInf=0.000, Recon=0.000).
- **Hybrid Advantage**: The use of BM25-guided candidate pre-filtering before encrypted scoring allows the system to focus computation on high-precision entity matches, sustaining high top-1 utility under encryption.
- **The Bandwidth Paradox**: Cryptographic score protection (HE) introduces an approximately **2,964x bandwidth overhead** (7.3KB → 21,667KB), identifying a critical practical bottleneck for decentralized semantic search.

## 3. Workshop Paper Status
The benchmarking phase is closed. The results are stable, consistent, and ready for publication:
- **Main Results Table**: Verified across 5 runs with stable latency (~2146ms for HE-Lite, ~2289ms for Combined ns=2.0).
- **Adaptive Attack Analysis**: Confirmed that rate-limiting is essential as averaging 10+ queries can fully erode noise protection (ASR→1.000 at ns=2.0).
- **Theoretical Framing**: Framing protection as empirical adaptive resistance for high-noise regimes ($\epsilon \approx 20,000$).
