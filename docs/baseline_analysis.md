# Phase 2 Baseline Analysis: The Optimization Journey

This document logs the experiments conducted to establish a strong, high-utility baseline for the Priva-Fed framework.

## initial Baseline (Plaintext FAISS)
- **Method**: `sentence-transformers/all-MiniLM-L6-v2` + FAISS `IndexFlatL2`
- **Result**:
    - Recall@1: 38.5%
    - Latency: ~19 ms
- **Analysis**: Low recall due to L2 distance on unnormalized vectors and lack of keyword matching for specific entities (Transaction IDs).

## Optimization 1: Normalization & Inner Product
- **Method**: L2 Normalization + `IndexFlatIP` (Cosine Similarity)
- **Result**:
    - Recall@1: 38.5% (No change)
    - Latency: ~18 ms
- **Analysis**: Normalization helps theoretical correctness but didn't solve the core issue of exact entity matching in synthetic data.

## Optimization 2: Hybrid Search (BM25 + RRF)
- **Method**: `rank_bm25` fused with Dense Retrieval using Reciprocal Rank Fusion (RRF).
- **Refinement**: Improved tokenizer to strip punctuation (e.g., handling "ID." at end of sentences).
- **Result**:
    - Recall@1: 66.7%
    - Recall@10: 73.3%
    - Latency: ~25 ms
- **Analysis**: Massive jump in recall. BM25 effectively captures exact IDs, while Dense vector captures semantic context. RRF robustly combines them.

## Optimization 3: Cross-Encoder Re-ranking + Neutral Queries (Final Baseline)
- **Method**: `cross-encoder/ms-marco-TinyBERT-L-2-v2` re-ranking top-20 RRF candidates.
- **Refinement**: Updated query templates to be neutral (e.g., "account {id} history" instead of "suspicious activity on..."). This forces reliance on specific entity matches.
- **Result**:
    - **Recall@1**: 91.9%
    - **Recall@10**: 97.8%
    - **Average Latency**: ~57 ms
- **Conclusion**:
    - Removing semantic bias in queries proved critical.
    - We have effectively solved the retrieval task for this dataset (near 100% recall).
    - **This creates a near-perfect "upper bound"** for our privacy experiments.

## Root Cause Analysis: The "Semantic Distraction" Problem
**Why was the recall initially low (~73%)?**
The initial query template was `"suspicious activity on account {ID}"`.
- **The Issue**: The phrase "suspicious activity" is semantically heavy. The retrieval models (both Dense and Sparse) prioritized documents containing this exact phrase (e.g., "Analyst Note: Suspicious activity detected...").
- **The Result**: The system retrieved *any* document mentioning "suspicious activity", often ignoring the specific `{ID}`.
- **The Fix**: Changing the query to `"account {ID} history"` removed the distracting semantic noise. The `{ID}` became the primary signal, forcing the system to retrieve the exact match.
- **Key Takeaway**: In hybrid search, unique identifiers must not be overshadowed by generic thematic keywords.

## Summary Table

| Method | Recall@1 | Recall@10 | Latency (ms) | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Dense (Base)** | 38.5% | 56.3% | ~19 | Fast, poor entity match |
| **Hybrid (RRF)** | 66.7% | 73.3% | ~25 | Biased queries |
| **Hybrid + Rerank (Final)** | **91.9%** | **97.8%** | ~57 | **Max Utility** |
