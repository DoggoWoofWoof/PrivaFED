# Priva-Fed Benchmarking Final Results — Workshop Paper Ready

This document presents the final, verified empirical evaluation of the Priva-Fed privacy-preserving retrieval pipeline. All results are now stable across multiple runs with no identified outliers.

## 1. Top-Level Defense Matrix

Neither defense alone is sufficient to protect against the diverse threat landscape of semantic retrieval. The combined pipeline is the strongest overall profile by fully blocking score-side attacks while partially reducing query fingerprinting.

| Mode | Query ASR | MIA Accuracy | Score Inference | Embedding Recon |
| :--- | :---: | :---: | :---: | :---: |
| **Plaintext** | 1.000 | 1.000 | 0.860 | 0.593 |
| **VS-ADP** | 0.720 | 1.000 | 0.820 | 0.581 |
| **HE-Lite** | 1.000 | 0.500 | 0.000 | 0.000 |
| **LSH** | 1.000 | 1.000 | 0.840 | 0.573 |
| **LSH+ADP** | 0.740 | 1.000 | 0.800 | 0.592 |
| **Combined** | **0.760** | **0.500** | **0.000** | **0.000** |

> [!IMPORTANT]
> **Score-side privacy is solved by HE-Lite/Combined** (MIA=0.500, ScoreInf=0.000, Recon=0.000), while query-side attacks remain partially successful (best ASR in this matrix: VS-ADP at 0.720).

## 2. Privacy-Utility Benchmark Results

Combined mode preserves or improves R@1 over the dense plaintext baseline while fully defending score-side channels, likely due to the "ensemble effect" of BM25-guided candidate selection prior to encrypted scoring.

| Mode | NS | R@1 | ASR | Latency | Bandwidth |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Plaintext** | — | 0.860±0.000 | 1.000 | 189ms | 7.3KB |
| **VS-ADP** | 0.1 | 0.852±0.023 | 1.000 | 198ms | 7.3KB |
| **VS-ADP** | 0.5 | 0.832±0.042 | 1.000 | 212ms | 7.3KB |
| **VS-ADP** | 1.0 | 0.844±0.022 | 0.956±0.022 | 220ms | 7.3KB |
| **VS-ADP** | 2.0 | 0.820±0.028 | 0.676±0.048 | 209ms | 7.3KB |
| **HE-Lite** | — | 0.940±0.000 | 1.000 | 2146ms | 21,667KB |
| **LSH** | — | 0.840±0.000 | 1.000 | 203ms | 7.3KB |
| **LSH+ADP** | 0.1 | 0.840±0.000 | 1.000±0.000 | 206ms | 7.3KB |
| **LSH+ADP** | 0.5 | 0.840±0.000 | 1.000±0.000 | 207ms | 7.3KB |
| **LSH+ADP** | 1.0 | 0.800±0.000 | 0.940±0.000 | 202ms | 7.3KB |
| **LSH+ADP** | 2.0 | 0.800±0.000 | 0.720±0.000 | 202ms | 7.3KB |
| **Combined** | 1.0 | 0.940±0.000 | 0.972±0.023 | 2065ms | 21,667KB |
| **Combined** | 2.0 | 0.940±0.000 | 0.636±0.017 | 2289ms | 21,667KB |

## 3. Adaptive Attack Resistance (ns=2.0)

Under repeated querying, the protection of VS-ADP can be eroded through vector averaging.

| N queries | ASR (ns=2.0) |
| :--- | :---: |
| 1 | 0.680 |
| 5 | 0.980 |
| 10 | 1.000 |
| 20 | 1.000 |

## 4. Recommended Operating Point

> [!TIP]
> **Recommended Point: Combined ns=2.0 for score confidentiality + utility, with strict query-rate controls.** 
> This configuration keeps MIA/ScoreInf/Recon fully blocked while reducing single-query ASR. However, adaptive averaging still recovers the query signal, so operational controls are required alongside model-side defenses.

## 5. Critical Paper Notes

*   **HE Accuracy & Pre-filtering**: HE-Lite/Combined achieve stable R@1 (0.940) by utilizing BM25-guided candidate pre-filtering before encrypted scoring. This concentrates computation on high-precision entity matches. The corresponding Drift score (~0.328) reflects that the overall HE ranking order diverges from the dense plaintext baseline, even as top-1 utility remains high.
*   **Epsilon Framing**: At noise scale ns=2.0, the system accumulates approximately $\epsilon \approx 21,235$ per query under RDP accounting. This operates outside the formal DP regime ($\epsilon < 10$). Consequently, the Budget-Aware Hub is framed as providing **empirical adaptive attack resistance** via rate-limiting rather than formal differential privacy guarantees at these noise levels.
*   **Bandwidth Overhead**: HE and combined modes incur an approximately **2,964x bandwidth overhead** (21,667 KB vs 7.3 KB). This figure represents the practical cost of cryptographic score protection and reflects actual TenSEAL CKKS serialized blob sizes measured directly during the benchmark.

## 6. Output Files
*   [results.csv](../results/results.csv)
*   [defense_matrix.csv](../results/defense_matrix.csv)
*   [attack_adaptive.csv](../results/attack_adaptive.csv)
