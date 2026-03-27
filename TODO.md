# Complete Future Work List

This document captures the complete and prioritized future work list emerging from the initial project completion phase.

---

## Priority Order If You Have Time After the Paper

| Priority | Item | Effort |
|---|---|---|
| 1 | LSH + ADP combination benchmark | 1 day |
| 2 | MS-MARCO scaling to 10+ nodes | 2-3 weeks |
| 3 | SOTA comparison (PRADA/SecureBERT) | 1-2 weeks |
| 4 | Formal top-k sensitivity derivation | 3-5 days math work |
| 5 | Chaff distribution matching | 1 week |
| 6 | Pass 1 leakage formal bound | 2-3 days |
| 7 | Scalability curves (3→50 nodes) | 1 week |
| 8 | Dynamic participation / threshold sharing | 1 month |

*(For the workshop paper due March 15, only item 1 (LSH+ADP) is realistically doable before submission. Everything else is correctly scoped as future work.)*

---

## Detailed breakdown of future tasks

### Category 1: Critical Blockers for Main Conference (Must Do)

- **MS-MARCO Scaling**: The single biggest gap. Currently 300 documents across 3 nodes. For any main conference submission (EMNLP, ACL) you need at minimum 10,000+ documents across 10+ nodes. The dataset is essentially a lookup table right now — reviewers know this. This was discussed as the #1 priority repeatedly across every iteration.
- **SOTA Comparison**: Direct benchmark against PRADA and SecureBERT. You have no numbers comparing your system against existing privacy-preserving retrieval papers. Reviewers at any main venue will reject without this. Currently scoped as future work.
- **Node Scalability Curves**: How does latency, bandwidth, and utility change as nodes scale from 3 to 10 to 50? Currently completely absent. With only 3 nodes you can't generalize any federated claim.

### Category 2: Formal Math Gaps (Should Do)

- **Top-K Ranking Sensitivity Formal Derivation**: Currently using Δf=2.0 per-score, but this is the per-score stability argument. The full ranking sensitivity under document replacement for top-k retrieval is an open formal question. The √k formula was introduced and then correctly identified as wrong. The right approach is a stability argument showing one document replacement changes at most one ranking position. This needs to be written out formally.
- **DP-SGD Comparison**: Reviewers will ask why you add noise at inference time rather than training with DP-SGD and comparing both approaches. You need an answer either as a comparison or as a justified design decision.
- **RDP Composition Across Both Passes**: The accountant tracks noise in Pass 2 but Pass 1 (candidate nomination) also leaks information. The full two-pass RDP budget should account for both interactions formally.

### Category 3: Your Specific New Idea — LSH + ADP Combination

This was not previously benchmarked. You currently have these modes: `plaintext`, `VS-ADP`, `HE-Lite`, `LSH`, and `Combined` (VS-ADP + HE + P2P). **LSH + ADP combined mode is missing.** 

The intuition is interesting — LSH reduces the information content of the query (binary fingerprint instead of 384 floats), then VS-ADP adds noise on top of the already-compressed representation. This might give a better privacy-utility tradeoff than either alone because:
- LSH already discards fine-grained directional information
- The noise only needs to obscure the coarser binary projection space
- Bandwidth stays at 7.3KB (unlike HE which is 21MB)

*To implement*: route the query through SimHash first, then add Gaussian noise to the binary projection values (or to the dense vector before hashing, which is more principled). Benchmark against the full attack suite. The hypothesis is ASR below combined's 0.672 at lower bandwidth cost than HE. This is genuinely worth testing as it could be a third operating point on the privacy-utility-bandwidth curve.

### Category 4: Security Limitations That Need Formal Treatment

- **Chaff Query Distribution Matching**: Currently heuristic, not formally proven. Proper fix requires sampling chaff from the empirical distribution of real query embeddings so nodes cannot distinguish by score distributions. Three paths: (1) distribution-matched chaff, (2) formal bound on distinguishing advantage, (3) switch to PIR protocols.
- **Pass 1 Candidate Pass Leakage**: Document nomination frequencies visible to the hub before masking. Over many queries the hub can statistically fingerprint corpus composition. Currently acknowledged as a known attack but not bounded or defended. Formal treatment would require either: (a) a bound on information gained per query from nomination patterns, or (b) using Private Information Retrieval for Pass 1.
- **Dynamic/Partial Node Participation**: Current architecture assumes all nodes participate in every query. Drop-out, selective querying, and dynamic federation membership all break the mask cancellation math. Threshold secret sharing (k-of-n nodes producing a valid result) is the cryptographic solution but significantly more complex.
- **Inference-Time vs Training-Time Privacy**: No comparison against DP-SGD trained retrievers. Needs at least a design justification if not an empirical comparison.

### Category 5: Engineering Improvements

- **Automatic Privacy Orchestrator**: An adaptive system that analyzes query sensitivity (is this a medical query? financial? general?) and automatically selects the appropriate privacy mode. General queries → LSH. Sensitive entity queries → Combined. This was identified as a potential novelty contribution but never built.
- **Formal Inference-Time Chaff Indistinguishability Test**: Run a KL-divergence or Maximum Mean Discrepancy (MMD) test comparing the embedding distribution of chaff queries versus real queries. Currently this is claimed heuristically without measurement.
- **Hardware Context Documentation**: Benchmark results currently have no hardware specification. Latency numbers are meaningless without CPU/RAM/network simulation specs stated clearly.
