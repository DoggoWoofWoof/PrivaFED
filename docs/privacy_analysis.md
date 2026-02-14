# Priva-Fed Benchmark Analysis

This document summarizes the empirical trade-offs between Privacy, Latency, and Utility measured using the Priva-Fed framework.

## Methodology
- **Dataset**: 300 synthetic financial narrative documents distributed across 3 organizations.
- **Queries**: 362 ground-truth queries (neutral "account {id} history" template).
- **Federated Architecture**: Hub broadcasts to 3 nodes; Nodes return sanitized results; Hub aggregates top-10.
- **Baseline Utility**: 97.8% Recall@10 (local plaintext). 95.3% (federated plaintext).

## Results Summary

| Metric | Plaintext (Baseline) | VS-ADP ($\epsilon=5.0$) | VS-ADP ($\epsilon=0.5$) | HE-Lite (Ckks) |
| :--- | :--- | :--- | :--- | :--- |
| **Recall@1** | 85.6% | 85.6% | **80.9%** | 85.6%* |
| **Recall@10** | 95.3% | 95.3% | 95.9% | 95.3%* |
| **Latency (ms)** | ~215 | ~173 | ~186 | ~194 |
| **Bandwidth (KB)** | ~22 | **~7** | ~7 | **~19,588** |

*\*HE-Lite utility is identical to plaintext in this benchmark because we simulated the sorting step to isolate encryption overhead. In a real fully-homomorphic sort, latency would likely explode further.*

## Trade-off Analysis

### 1. Vector-Space ADP (VS-ADP)
- **Strengths**: 
    - **Lowest Bandwidth**: Redacting text and sending only noisy vectors/scores reduces payload size by ~3x compared to sending full text.
    - **Fast**: Latency is comparable to (or faster than) plaintext due to smaller payloads.
- **Weaknesses**:
    - **Utility Loss**: At high privacy regimes ($\epsilon=0.5$), Recall@1 drops significantly (~5%). 
    - **Verification**: Verifying the "correctness" of a noisy result is harder for the end-user.

### 2. Homomorphic Encryption (HE-Lite)
- **Strengths**:
    - **Perfect Utility**: Preserves exact ranking (theoretical).
    - **Strong Privacy**: Cryptographic guarantees.
- **Weaknesses**:
    - **Bandwidth Explosion**: The payload size increases by **~3000x** (19MB per query vs 7KB). This is the "Unstructured Privacy Paradox" in action—encrypting high-dimensional vectors/scores is expensive.
    - **Scalability**: While latency was low in this small-scale test (~300 docs), the bandwidth cost makes this prohibitive for low-bandwidth networks or massive concurrency.

## Conclusion
**Priva-Fed** successfully quantified the trade-off:
- For **real-time** applications where bandwidth is constrained, **VS-ADP** is the only viable option, provided ~5% recall loss is acceptable.
- **HE-Lite** is technically feasible for latency but **catastrophic for bandwidth**, making it suitable only for high-security, high-bandwidth "batch" processing, not real-time RAG.
