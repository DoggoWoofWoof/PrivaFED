# Attack Types in Priva-Fed: How They Work and Why Defenses Work

This document explains the attack taxonomy implemented in Priva-Fed, how each attack works step-by-step, what attacker access is required, how success is measured, and which privacy mechanism is intended to stop it.

The content below is grounded in the implementation in:
- src/attack.py
- src/privacy.py
- src/hub.py
- src/local_retrieval.py
- src/benchmark_full.py

## 1) System Surfaces an Attacker Can Observe

Priva-Fed runs a multi-pass retrieval protocol:

1. Pass 1 (candidate gathering): nodes return candidate document descriptors.
2. Pass 2 (score aggregation): nodes score union candidates and hub aggregates masked scores.
3. Pass 3 (content fetch): final top-k contents are fetched.

This creates two main attack surfaces:

- Query-side surface: intercepted query embeddings/vectors on hub-to-node paths.
- Score-side surface: intercepted relevance scores (or metadata derived from score behavior).

## 2) Attack Taxonomy Used in This Repo

Attacks are split into two categories in src/attack.py.

## 2.1 Category A: Query-Vector Attacks

Goal: infer the user intent or exact target document from intercepted query vectors.

### A1. Known Template Attack

Class: KnownTemplateAttack

Idea:
- The attacker pre-builds a "fingerprint index" of likely query templates.
- When a live query vector is observed, attacker nearest-neighbor matches it to the fingerprint bank.

How it works in code:

1. Build fingerprints from extracted ground truth queries.
2. Encode all fingerprint queries with the same sentence encoder.
3. Normalize and index in FAISS IndexFlatIP.
4. On interception, normalize observed vector and search top-1 or top-k.
5. Attack succeeds if predicted org/file equals true org/file.

Why it is effective:
- If query vectors are deterministic and high-dimensional, nearest-neighbor fingerprinting can be very accurate.

What defends it:
- VS-ADP noise in src/privacy.py (PrivacyAdapter.add_noise_to_vector).
- Optional k-anonymity/chaff in src/hub.py (HubOrchestrator.k_anonymity).

Main metric:
- Attack Success Rate (ASR@1, ASR@5).

### A2. Multi-Query Averaging Attack (Adaptive)

Class: MultiQueryAveragingAttack

Idea:
- If attacker can observe multiple noisy realizations of the same logical query, averaging cancels random noise.

How it works in code:

1. Generate N noisy query vectors for the same query text.
2. Average them into one vector.
3. Normalize averaged vector.
4. Run KnownTemplateAttack on the averaged vector.

Why it is effective:
- Gaussian noise averages out with repeated observations.
- Per-dimension noise variance reduces approximately with 1/N.
- Signal-to-noise ratio improves as sqrt(N).

What defends it:
- Rate-limiting and budget enforcement (epsilon limits in PrivacyAccountant + Hub budget checks).
- Chaff/k-anonymity so repeated real queries are harder to isolate.

Main metric:
- ASR as a function of N observations (see results/attack_adaptive.csv).

## 2.2 Category B: Score and Transit Attacks

Goal: infer membership, relevance profiles, or reconstruct document embeddings from score behavior.

### B1. Membership Inference Attack (MIA)

Class: MembershipInferenceAttack

Idea:
- Use maximum score patterns to predict if a document/entity is in a target node corpus.

How it works in code:

1. Collect score distributions for member and non-member queries.
2. Learn a threshold that maximizes classification accuracy.
3. Predict "member" when max_score >= threshold.

Why it is effective:
- Raw similarity scores often shift measurably when target data is present.

What defends it:
- HE-Lite score encryption so hub/adversary cannot observe raw score values.
- In encrypted modes, benchmark models attacker as random guess (accuracy about 0.5).

Main metric:
- MIA accuracy (ideal defense: close to 0.5).

### B2. Score Inference Attack

Class: ScoreInferenceAttack

Idea:
- Intercept ranked (org, filename, score) tuples over time and build relevance profiles.

How it works in code:

1. Intercept query plus ranked results with scores.
2. For each query, infer likely top target from ranked scores.
3. Compare inferred top-1 with ground truth.

Why it is effective:
- Continuous score leakage exposes stable ranking signatures.

What defends it:
- HE-Lite/combined mode marks interceptions as encrypted; no usable scores are logged.

Main metric:
- Profile accuracy against ground truth (ScoreInf).

### B3. Embedding Reconstruction Attack

Class: EmbeddingReconstructionAttack

Idea:
- Probe a target with random vectors; use observed dot-product scores to reconstruct target embedding.

How it works in code:

1. Sample n_probes random normalized probe vectors.
2. Query score oracle for each probe against target embedding.
3. Reconstruct by weighted sum of probes using observed scores.
4. Normalize reconstructed vector.
5. Evaluate cosine similarity to true embedding.

Why it is effective:
- Dot products reveal linear projections; many projections can recover direction of target embedding.

What defends it:
- HE-Lite hides oracle outputs (scores not visible to attacker).
- In benchmark encrypted setting, oracle effectively returns no informative score.

Main metric:
- Reconstruction cosine similarity (ideal defense: near 0).

## 3) How Privacy Mechanisms in privacy.py Interrupt Attack Chains

## 3.1 VS-ADP (Vector-Space Noise)

Location: PrivacyAdapter.add_noise_to_vector

Mechanism:
- For embedding dimension d, sigma_per_dim = noise_scale / sqrt(d).
- Add Gaussian noise N(0, sigma_per_dim^2).
- Renormalize to unit L2 norm.

Security effect:
- Breaks deterministic template matching in Category A.
- Does not directly hide score channels in Category B.

Important limitation:
- Vulnerable to adaptive averaging when the same logical query is observed repeatedly.

## 3.2 Privacy Budget Accounting (RDP)

Location: PrivacyAccountant in src/privacy.py

Mechanism:
- Tracks per-query RDP epsilon contribution over alpha grid.
- Uses sensitivity=2.0, and optionally two passes for multi-pass use.
- Composes linearly in RDP space.
- Converts to epsilon,delta form by:
  epsilon(alpha) = total_rdp(alpha) + log(1/delta)/(alpha-1)

Security effect:
- Enables operational stopping/rate-control when epsilon exceeds configured limit.

Important limitation:
- At high noise settings used for empirical resistance, epsilon can still accumulate rapidly.

## 3.3 HE-Lite (CKKS)

Location: PrivacyAdapter._init_he and encryption methods

Mechanism:
- Encrypt query vectors and/or scores with TenSEAL CKKS context.
- Perform encrypted dot product (ciphertext query x plaintext doc vector).

Security effect:
- Eliminates raw score visibility, which directly breaks MIA, score inference, and embedding reconstruction from score probes.

Important trade-off:
- High latency and bandwidth overhead in benchmark results.

## 3.4 LSH (SimHash)

Location: PrivacyAdapter.compute_lsh and LocalNode.search LSH branch

Mechanism:
- Project vectors into bit signatures.
- Use Hamming similarity instead of dense dot products.

Security effect:
- Lightweight score obfuscation baseline.

Important limitation:
- Non-cryptographic; does not provide the same confidentiality guarantees as HE.

## 3.5 Secure Aggregation (P2P Masking)

Location: LocalNode.generate_p2p_mask and score_candidates

Mechanism:
- Pairwise shared secrets generate additive/subtractive masks.
- Masks cancel when hub sums all node contributions.

Security effect:
- Hub only sees aggregate sum, not each node's raw local contribution.

Important limitation:
- Pass 1 candidate metadata can still expose some structural information.

## 4) Defense Coverage Matrix (Conceptual)

| Attack | Main leaked signal | Primary defense | Why defense helps |
|---|---|---|---|
| Known Template | Query vectors | VS-ADP | Noise perturbs nearest-neighbor fingerprints |
| Multi-Query Averaging | Repeated noisy vectors | Budget + rate controls + chaff | Limits ability to average many samples |
| MIA | Raw score magnitude patterns | HE-Lite | Removes attacker access to plaintext scores |
| Score Inference | Ranked score tuples | HE-Lite | Removes useful score telemetry |
| Embedding Reconstruction | Probe-response dot products | HE-Lite | Blocks linear projection observations |

## 5) Metrics to Report for Each Attack Family

Category A (query-side):
- ASR@1 and ASR@5
- Recon Error between plain and noisy query vectors (1 - cosine similarity)
- Adaptive ASR curve versus number of observations

Category B (score-side):
- MIA accuracy (defended target close to 0.5)
- Score inference profile accuracy
- Embedding reconstruction cosine similarity

System-level costs:
- Latency per query
- Bandwidth per query

## 6) Practical Interpretation for Experiments

- If ASR drops but recovers quickly with averaging, query-side defense is only single-shot robust.
- If MIA, ScoreInf, and Recon collapse to random/zero under HE modes, score-side confidentiality is working.
- If utility remains high while score-side attacks fail, the pipeline is achieving a useful privacy-utility balance.

## 7) Reproducibility Pointers

To regenerate attack-related outputs:

1. Run benchmark: python src/benchmark_full.py
2. Inspect aggregate metrics: results/results.csv
3. Inspect attack matrix: results/defense_matrix.csv
4. Inspect adaptive attack curve: results/attack_adaptive.csv

## 8) Known Residual Risks

1. Adaptive repeated-query attackers can reduce noise protection over time.
2. Metadata leakage can remain even when raw scores are protected.
3. Non-cryptographic methods (LSH) should be treated as approximation baselines, not full confidentiality controls.

## 9) Bottom Line

Priva-Fed attacks separate cleanly into:
- Query reconstruction/fingerprinting attacks (Category A), best handled by VS-ADP plus operational controls.
- Score and oracle attacks (Category B), best handled by HE-Lite and secure aggregation.

No single mechanism is sufficient in isolation; the strongest posture is layered defenses plus operational guardrails.