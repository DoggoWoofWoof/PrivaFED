# Baseline Analysis: Establishing the Upper Bound

This document logs the development of the high-utility retrieval baseline for the Priva-Fed framework. Establishing a strong baseline is critical for measuring the true "cost" of privacy.

## Establishing the Gold Standard

Initially, the system used a simple Dense Retrieval approach (FAISS + all-MiniLM-L6-v2), which achieved suboptimal recall (~40%) due to the difficulty of matching specific entities (like account numbers) in unstructured financial narratives.

### Optimization 1: Hybrid Retrieval (Dense + BM25)
By merging FAISS dense vector search with BM25 keyword matching using Reciprocal Rank Fusion (RRF), utility improved significantly. BM25 catches the precise entity IDs that dense vectors sometimes overlook.

### Optimization 2: SOTA Re-ranking (Cross-Encoder)
The final baseline incorporates a `cross-encoder/ms-marco-TinyBERT-L-2-v2` re-ranking step. This model analyzes the full query-document pair for semantic relevance, bringing the most relevant results to the top.

## Final Verified Baseline Performance

The finalized plaintext baseline (without any privacy mechanisms) serves as our performance ceiling:

| Metric | Value |
| :--- | :--- |
| **Recall@1** | 0.900 |
| **Recall@10** | 1.000 |
| **Mean Latency** | 293ms |
| **Bandwidth** | 7.3KB |

### Key Takeaway: Neutrality is Utility
Early experiments showed that semantic "noise" in query templates (e.g., using terms like "suspicious activity") biased results. Switching to neutral, entity-focused templates (e.g., "account {id} history") was the single most effective way to reach the 90% R@1 ceiling.
