# Priva-Fed Metrics Explanation

This document explains the metrics used to benchmark the privacy-utility trade-off.

## 1. Utility Metrics (Does the system still work?)

These measure how much the privacy noise damages the search quality.

| Metric | Definition | Why it matters |
|---|---|---|
| **R@1 (Recall at 1)** | The percentage of queries where the *exact correct document* appeared at the #1 position. | Captures "perfect" retrieval. If this drops, users lose trust immediately. |
| **R@10 (Recall at 10)** | The percentage of queries where the correct document appeared anywhere in the top 10 results. | Captures "good enough" retrieval. Shows if the document is at least *findable*. |
| **MRR (Mean Reciprocal Rank)** | The average of (1 / rank) of the correct result. If correct doc is #1 → 1.0. If #2 → 0.5. If #10 → 0.1. | Penalizes lower rankings more heavily than Recall. A standard IR metric. |
| **NDCG@10** | **Normalized Discounted Cumulative Gain**. Similar to MRR but handles multiple relevant docs (though we only have 1 true target). | The "gold standard" ranking metric in academic papers. |
| **Semantic Drift** | Measures how much the *list of results changed* compared to the plaintext baseline. Calculated as the overlap between the noisy top-10 and the clean top-10. | **Consistency Check**. If R@10 is high but Drift is high, it means we found the right doc but the *other* 9 docs are completely random/different. |
| **Rank Correlation** | Kendall's Tau correlation between the *scores* of the baseline vs. noisy results. | Application-specific stability. |

## 2. Privacy Metrics (Is the data safe?)

These measure how successfully an attacker can steal information. Lower is better.

### Category A: Query Attacks (Targeting the User's Intent)
*Defended by VS-ADP (Adding noise to query)*

| Metric | Definition | Interpretation |
|---|---|---|
| **ASR (Attack Success Rate)** | The percentage of *interviews* where the attacker correctly identified the exact original query template and entity ID from the noisy vector. | **1.000 (100%)** = Total breach. Attacker knows exactly what you asked.<br>**0.000 (0%)** = Perfect privacy. |
| **Query Reconstruction Error** | Cosine distance between the original query vector and the noisy vector. | Proxy for how "garbled" the query is. |

### Category B: Score Attacks (Targeting the Database Contents)
*Defended by HE-Lite (Encrypting scores)*

| Metric | Definition | Interpretation |
|---|---|---|
| **MIA (Membership Inference)** | **Membership Inference Attack Accuracy**. Can the attacker tell if a specific document exists in the database by seeing the score it returns? | **0.84** = High risk. Attacker can guess membership.<br>**0.50** = Random coin flip (Perfect Privacy). |
| **ScoreInf** | **Score Inference Accuracy**. Can the attacker deduce which document was retrieved just by looking at the raw score values? | **0.866** = Attacker identifies doc by score alone.<br>**0.000** = Scores are encrypted/hidden. |
| **Recon CosSim** | **Embedding Reconstruction Cosine Similarity**. Can the attacker reverse-engineer the *content* (text vector) of a document by analyzing the scores it produces for many queries? | **0.58** = Partial reconstruction (can verify keywords).<br>**0.00** = Impossible to reconstruct. |

## 3. System Metrics (Is it practical?)

| Metric | Definition | Trade-off |
|---|---|---|
| **Latency (ms)** | Time taken to return results to the user. | Privacy adds computation (encryption/decryption). |
| **Bandwidth (KB)** | Amount of data transmitted per query. | Privacy adds data bloat (ciphertexts are larger than floats). |

## Summary of Results

| Feature | Best Metric Value | Achieved By |
|---|---|---|
| **Best Utility** | R@1 = 0.866 | Plaintext / HE-Lite |
| **Best Query Privacy** | ASR = 0.647 | VS-ADP (ns=2.0) |
| **Best Data Privacy** | MIA = 0.500 | HE-Lite |
| **Best Overall Balance** | Mixed | **Combined Pipeline** |
