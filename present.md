# Priva-Fed Presentation

## Slide 1: Title
**Priva-Fed: Benchmarking Privacy-Utility Trade-offs in Federated Semantic Retrieval**

- Domain: Privacy-preserving retrieval over unstructured data
- Context: Federated setting across multiple organizations
- Core question: Can we protect privacy without killing retrieval quality?

---

## Slide 2: Problem Statement
### What problem are we solving?
Organizations need to search sensitive unstructured records across data silos, but query embeddings and relevance scores can leak private information.

### Why does it matter?
- Real industries (finance, healthcare, enterprise) cannot centralize raw data.
- Leaks in retrieval channels can expose user intent and corpus membership.
- Existing systems usually optimize either privacy or utility, not both.

---

## Slide 3: Objective
- Build a federated benchmark that jointly measures **utility, privacy, and system cost**.
- Evaluate multiple privacy mechanisms under **real attack simulations**.
- Identify a practical operating point for high utility with strong privacy defense.

---

## Slide 4: Proposed Solution
Priva-Fed uses a **defense-in-depth** architecture:

- VS-ADP for query embedding obfuscation
- HE-Lite (CKKS) for score confidentiality
- LSH as a lightweight baseline
- P2P masking for secure score aggregation

### How GenAI is used
- Dense semantic retrieval with transformer embeddings
- Cross-encoder reranking for high-precision ranking
- Pipeline is retrieval-ready for downstream LLM answer synthesis

---

## Slide 5: System Architecture
### High-level flow
**Input Query -> Hub Orchestrator -> Privacy Adapter -> Local Nodes -> Secure Aggregation -> Top-k Results -> Output**

### Components to show in diagram
- Input/API layer: Hub broadcast + coordination
- Processing layer: Embedding, FAISS/BM25, reranking, privacy transforms
- Security layer: HE + VS-ADP + masking
- Output layer: Ranked results (and optional LLM synthesis)

### 3-pass protocol
1. Candidate gathering
2. Masked/encrypted score aggregation
3. Content fetch for final top-k only

---

## Slide 6: Tech Stack
- **Language:** Python
- **Retrieval:** FAISS, BM25 (rank_bm25), Reciprocal Rank Fusion
- **Models:** all-MiniLM-L6-v2, ms-marco-TinyBERT-L-2-v2
- **Privacy:** TenSEAL CKKS, Gaussian noise (VS-ADP), SimHash (LSH), P2P masking
- **Data generation:** Faker-based synthetic narrative generator

---

## Slide 7: Working / Methodology
1. User sends query to hub
2. Hub creates embedding
3. Privacy mode is applied (Plaintext / VS-ADP / HE / LSH / Combined)
4. Nodes run hybrid search (dense + sparse + rerank)
5. Nodes return masked/encrypted scores
6. Hub aggregates and ranks final top-k
7. Privacy and utility metrics are logged

---

## Slide 8: Results / Evaluation
### Utility and system performance
- Plaintext baseline: **R@1 = 0.860**, Latency ~189 ms, BW 7.3 KB
- Combined (ns=2.0): **R@1 = 0.940**, Latency ~2289 ms, BW 21667 KB

### Privacy outcomes
- HE/Combined block score-side channels:
  - MIA = 0.500 (random guess)
  - Score inference = 0.000
  - Embedding reconstruction = 0.000
- VS-ADP reduces single-query fingerprinting ASR at high noise, but not fully.

### Trade-off highlight
- Strong score confidentiality comes with around **2964x bandwidth overhead**.

---

## Slide 9: Challenges Faced
- Query-side adaptive attacks (averaging repeated observations)
- Retrieval quality drift under stronger noise
- High latency and bandwidth in encrypted modes
- Pass-1 metadata leakage risk
- Formal DP interpretation limits at high practical epsilon

---

## Slide 10: Future Scope
- Add intelligent privacy orchestrator/agent per query sensitivity
- Improve adaptive attack resistance with stronger operational controls
- Scale to larger corpora and more nodes
- Add stronger pass-1 leakage defenses
- Production deployment with policy control and monitoring

---

## Slide 11: Conclusion
- Priva-Fed demonstrates that high-utility private federated retrieval is achievable.
- No single mechanism is enough; layered defenses are required.
- Final takeaway: privacy gains are real, but cryptographic cost is the key deployment bottleneck.

---

## Quick Demo Script (Optional)
- Start with baseline numbers (R@1 0.860)
- Show Combined mode gains (R@1 0.940 + score-side protection)
- End with paradox: privacy is stronger, but bandwidth jumps massively
- Close with roadmap: adaptive controls + scale-up + production hardening
