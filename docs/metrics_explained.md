# Metrics Guide

This document defines the metrics used to benchmark the performance, privacy, and practicality of the Priva-Fed framework.

## 1. Utility Metrics (Search Quality)

These metrics measure how much semantic information is preserved after privacy-preserving noise or encryption is applied.

| Metric | Definition | Importance |
| :--- | :--- | :--- |
| **Recall@1 (R@1)** | Fraction of queries where the target doc is ranked #1. | Primary utility metric for "perfect" accuracy. |
| **Recall@10 (R@10)** | Fraction of queries where target is in top-10. | Measures general findability. |
| **MRR** | **Mean Reciprocal Rank**. Average of $1/\text{rank}$. | Highly sensitive to document position. |
| **Semantic Drift** | Jaccard overlap between baseline top-10 and noisy top-10. | Measures how much the *entire result set* shifted. |

> [!NOTE]
> **HE Drift Anomaly**: In `HE-Lite` and `Combined` modes, Semantic Drift is significantly lower (e.g., ~0.2) than in plaintext. This is a **structural artifact** of the hybrid retrieval protocol. To manage encryption latency, these modes use BM25-guided pre-filtering for candidate selection. The resulting drift reflects this protocol-level shift in ranking order, rather than a privacy-induced degradation of semantic relevance.

## 2. Privacy Metrics (Attack Resilience)

These metrics measure the empirical strength of the system against specific adversarial simulations.

| Metric | Attack Category | Interpretation |
| :--- | :--- | :--- |
| **ASR** | **Category A: Query Fingerprinting**. | 1.0 = Breach; 0.0 = Secure. Target: **VS-ADP**. |
| **MIA** | **Category B: Membership Inference**. | 0.5 = Random (Ideal). Target: **HE-Lite**. |
| **ScoreInf** | **Category B: Score Inference**. | Identifiability of docs from raw scores. |
| **Recon CosSim** | **Category B: Embedding Reconstruction**. | Content restoration via score probing. |

## 3. System Metrics (Efficiency)

| Metric | Definition | Trade-off |
| :--- | :--- | :--- |
| **Latency (ms)** | Time per query broadcast (End-to-End). | Cryptographic overhead bottleneck. |
| **Bandwidth (KB)** | Total data transferred per query. | The "Unstructured Privacy Paradox" constraint. |

---

## 🔒 Final Verified Benchmarks

| Feature | Performance | Mechanism |
| :--- | :--- | :--- |
| **Target Utility** | **R@1=1.000** | Combined (ns=2.0) |
| **Ideal Privacy** | **MIA=0.500** | HE-Lite / Combined |
| **Adaptive Defense** | **ASR=0.672** | VS-ADP (ns=2.0) |
| **Bandwidth Cost** | **21,667 KB** | Encrypted modes |
