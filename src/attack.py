"""
Privacy Attack Simulation Suite for Priva-Fed.

Organized by WHAT the attacker intercepts:

Category A — Query-Vector Attacks (defended by VS-ADP noise):
  A1. KnownTemplateAttack: Fingerprint-match noisy query embedding
  A2. MultiQueryAveragingAttack: Average N noisy observations to denoise

Category B — Score/Transit Attacks (defended by HE-Lite encryption):
  B1. MembershipInferenceAttack: From raw scores, determine if a target
      document exists in a node's corpus
  B2. ScoreInferenceAttack: From raw scores + query, reconstruct
      document relevance profiles
  B3. EmbeddingReconstructionAttack: From many (query, score) pairs,
      reconstruct document embeddings via gradient-free optimization

This creates the defense matrix:
  +------------------+----------+----------+----------+
  |                  | Plaintext| VS-ADP   | HE-Lite  |
  +------------------+----------+----------+----------+
  | Query Attacks    | Vuln.    | Defended | Vuln.    |
  | Score Attacks    | Vuln.    | Vuln.    | Defended |
  | Combined         | Vuln.    | Partial  | Partial  |
  | VS-ADP + HE     | N/A      | N/A      | Full     |
  +------------------+----------+----------+----------+
"""

import numpy as np
import faiss
from src.ground_truth import extract_ground_truth


# ═══════════════════════════════════════════════════════════════════════
# CATEGORY A: Query-Vector Attacks (VS-ADP defends)
# ═══════════════════════════════════════════════════════════════════════

class KnownTemplateAttack:
    """
    Strongest query-level attack (SOTA-inspired).
    
    Attacker pre-generates ALL possible queries from leaked corpus,
    encodes them, and matches against intercepted (noisy) query vector.
    
    Plaintext ASR = 100%. Degrades with VS-ADP noise.
    HE-Lite provides NO defense (query vector is unencrypted).
    """

    def __init__(self, nodes, encoder_model):
        self.model = encoder_model
        self.fingerprints = []
        data_roots = {node.org_name: node.data_dir for node in nodes}
        gt = extract_ground_truth(data_roots)

        queries = []
        for item in gt:
            self.fingerprints.append(
                (item['target_org'], item['target_file'], item['query']))
            queries.append(item['query'])

        print(f"[KnownTemplateAttack] Encoding {len(queries)} candidate queries...")
        vecs = self.model.encode(queries).astype('float32')
        faiss.normalize_L2(vecs)
        self.index = faiss.IndexFlatIP(vecs.shape[1])
        self.index.add(vecs)
        print(f"[KnownTemplateAttack] Fingerprint index: {self.index.ntotal} vectors.")

    def attack(self, query_vector, target_org, target_file):
        vec = query_vector.copy().astype('float32').reshape(1, -1)
        faiss.normalize_L2(vec)
        scores, indices = self.index.search(vec, 1)
        org, fn, _ = self.fingerprints[int(indices[0][0])]
        return (org == target_org and fn == target_file), float(scores[0][0])

    def attack_top_k(self, query_vector, target_org, target_file, k=5):
        vec = query_vector.copy().astype('float32').reshape(1, -1)
        faiss.normalize_L2(vec)
        scores, indices = self.index.search(vec, k)
        for rank, idx in enumerate(indices[0]):
            org, fn, _ = self.fingerprints[int(idx)]
            if org == target_org and fn == target_file:
                return True, rank + 1
        return False, -1


class MultiQueryAveragingAttack:
    """
    Adaptive attacker averages N noisy query observations to denoise.
    
    More observations -> noise variance decreases by 1/sqrt(N).
    Defense: Query rate-limiting, budget constraints.
    """

    def __init__(self, template_attack, privacy_adapter, ref_node):
        self.template_attack = template_attack
        self.pa = privacy_adapter
        self.ref_node = ref_node

    def attack_with_n_observations(self, query_text, target_org, target_file, n=1):
        plain_vec = self.ref_node.encode_query(query_text)
        noisy_vecs = [self.pa.add_noise_to_vector(plain_vec.copy()) for _ in range(n)]
        avg_vec = np.mean(noisy_vecs, axis=0).astype('float32')
        faiss.normalize_L2(avg_vec.reshape(1, -1))
        return self.template_attack.attack(avg_vec, target_org, target_file)


# ═══════════════════════════════════════════════════════════════════════
# CATEGORY B: Score/Transit Attacks (HE-Lite defends)
# ═══════════════════════════════════════════════════════════════════════

class MembershipInferenceAttack:
    """
    Membership Inference Attack (MIA).
    
    Threat model: Attacker intercepts (query, raw_scores) from a node.
    Goal: Determine if a specific target document is in that node's corpus.
    
    Method: If the max score for a query targeting document D exceeds a
    threshold, attacker concludes D is in the corpus.
    
    Plaintext: High scores for members, lower for non-members -> vulnerable.
    HE-Lite: Scores encrypted in transit -> attacker sees ciphertext blobs.
    VS-ADP: Scores are real (noise is on query, not scores) -> still vulnerable.
    """

    def __init__(self, threshold=0.5):
        self.threshold = threshold

    def calibrate(self, member_scores, nonmember_scores):
        """
        Set threshold to maximize accuracy.
        member_scores: max scores when querying for documents IN the corpus.
        nonmember_scores: max scores when querying for documents NOT in the corpus.
        """
        all_data = [(s, 1) for s in member_scores] + [(s, 0) for s in nonmember_scores]
        all_data.sort(key=lambda x: x[0])

        best_acc, best_thresh = 0.0, 0.5
        for i in range(len(all_data)):
            thresh = all_data[i][0]
            tp = sum(1 for s, l in all_data if l == 1 and s >= thresh)
            tn = sum(1 for s, l in all_data if l == 0 and s < thresh)
            acc = (tp + tn) / len(all_data)
            if acc > best_acc:
                best_acc = acc
                best_thresh = thresh
        self.threshold = best_thresh
        return best_thresh, best_acc

    def attack(self, max_score):
        """Given max similarity score for a query, predict membership."""
        return max_score >= self.threshold


class ScoreInferenceAttack:
    """
    Score Inference Attack.
    
    Threat model: Eavesdropper intercepts (query, document_scores) in transit.
    Goal: Build relevance profiles — which documents are relevant to which queries.
    
    Method: For each intercepted (query, scores) pair, rank documents by score.
    Over many queries, build a document-query relevance matrix.
    A document's relevance profile reveals its content.
    
    Plaintext: Full raw scores visible -> attacker gets exact relevance matrix.
    HE-Lite: Scores encrypted -> attacker gets no information.
    VS-ADP: Scores are real (noise on query causes imprecise retrieval,
            but returned scores are exact) -> still partially vulnerable.
    
    Metric: Profile Accuracy = fraction of correctly identified top-1 documents
    across all intercepted queries.
    """

    def __init__(self):
        self.intercepted = []  # list of (query_text, [(org, filename, score)])

    def intercept(self, query_text, results, encrypted=False):
        """
        Record an intercepted query-response pair.
        If encrypted=True, attacker sees only ciphertext -> no useful info.
        """
        if encrypted:
            # Attacker sees opaque ciphertext blob
            self.intercepted.append((query_text, None))
        else:
            ranked = sorted(
                [(r['org'], r['filename'], r['score']) for r in results],
                key=lambda x: x[2], reverse=True
            )
            self.intercepted.append((query_text, ranked))

    def compute_profile_accuracy(self, ground_truth):
        """
        For each intercepted query, check if the top-1 result matches
        the ground truth target document.
        
        Returns: accuracy (float), n_usable (int)
        """
        correct, total = 0, 0
        gt_lookup = {item['query']: (item['target_org'], item['target_file'])
                     for item in ground_truth}

        for query, ranked in self.intercepted:
            if ranked is None:
                continue  # Encrypted — attacker learns nothing
            if query not in gt_lookup:
                continue
            total += 1
            target_org, target_file = gt_lookup[query]
            if ranked and ranked[0][0] == target_org and ranked[0][1] == target_file:
                correct += 1

        accuracy = correct / total if total > 0 else 0.0
        return accuracy, total


class EmbeddingReconstructionAttack:
    """
    Embedding Reconstruction via Score Probing.
    
    Threat model: Attacker can issue arbitrary queries and observe exact scores.
    Goal: Reconstruct a target document's embedding from (query, score) pairs.
    
    Method (simplified gradient-free):
    1. Issue K random probe queries
    2. Observe similarity scores s_i = cos(probe_i, target_emb)
    3. Solve for target_emb using least-squares on the cosine constraints
    
    This is the strongest score-based attack. Even partial score visibility
    enables reconstruction.
    
    Plaintext: Full scores -> full reconstruction
    HE-Lite: Encrypted scores -> reconstruction impossible
    VS-ADP: Scores are real but from noisy queries -> partial reconstruction
    """

    def __init__(self, embedding_dim=384, n_probes=100):
        self.d = embedding_dim
        self.n_probes = n_probes

    def attack(self, score_oracle, true_embedding=None):
        """
        score_oracle: function(query_vec) -> similarity score for target doc
        true_embedding: ground truth for measuring reconstruction quality
        
        Returns: reconstructed_embedding, cosine_sim_to_true
        """
        # Generate random probe queries
        probes = np.random.randn(self.n_probes, self.d).astype('float32')
        faiss.normalize_L2(probes)

        # Observe scores
        scores = np.array([score_oracle(probes[i]) for i in range(self.n_probes)])

        # Least-squares reconstruction: target ~= sum(score_i * probe_i)
        # This is a projection-based approximation
        reconstructed = np.zeros(self.d, dtype='float32')
        for i in range(self.n_probes):
            reconstructed += scores[i] * probes[i]
        reconstructed = reconstructed.reshape(1, -1)
        faiss.normalize_L2(reconstructed)
        reconstructed = reconstructed.flatten()

        cos_sim = 0.0
        if true_embedding is not None:
            true_flat = true_embedding.flatten()
            cos_sim = float(np.dot(reconstructed, true_flat) /
                           (np.linalg.norm(reconstructed) * np.linalg.norm(true_flat) + 1e-10))

        return reconstructed, cos_sim


def compute_reconstruction_error(original_vec, noisy_vec):
    """Cosine distance: 0 = identical, 1 = orthogonal."""
    a = original_vec.flatten()
    b = noisy_vec.flatten()
    cos_sim = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10)
    return 1.0 - cos_sim
