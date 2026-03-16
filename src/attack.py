"""
Adversarial Simulation Suite for the Priva-Fed Retrieval System.

This module implements the "Red Team" attacks used to empirically evaluate the
system's privacy guarantees. Attacks are categorized by the information intercepted
by the adversary.

Category A — Query-Vector Attacks (Defended by VS-ADP Noise):
   - KnownTemplateAttack: A state-of-the-art inspired fingerprinting attack that matches
     noisy query embeddings against a pre-encoded leaked corpus.
   - MultiQueryAveragingAttack: An adaptive attack where the adversary averages
     multiple noisy query observations to reduce noise variance.

Category B — Score and Transit Attacks (Defended by HE-Lite Encryption):
   - MembershipInferenceAttack (MIA): Predicting if a specific document exists in 
     a node's corpus by analyzing raw similarity scores.
   - ScoreInferenceAttack: Reconstructing relevance profiles from intercepted 
     document-query scores.
   - EmbeddingReconstructionAttack: A powerful score-probing attack that reconstructs
     a target document's embedding via least-squares optimization.
"""

import numpy as np
import faiss
from src.ground_truth import extract_ground_truth


# ═══════════════════════════════════════════════════════════════════════
# CATEGORY A: Query-Vector Attacks (Target: VS-ADP)
# ═══════════════════════════════════════════════════════════════════════

class KnownTemplateAttack:
    """
    Simulates an adversary with access to the document corpus but not the retrieval index.
    
    The attacker pre-generates a set of 'fingerprint' queries from the corpus.
    When a user query is intercepted, the attacker finds the closest fingerprint.
    """

    def __init__(self, nodes, encoder_model):
        """
        Args:
            nodes: List of nodes to build the fingerprint index from.
            encoder_model: The SentenceTransformer model used for encoding.
        """
        self.model = encoder_model
        self.fingerprints = []
        data_roots = {node.org_name: node.data_dir for node in nodes}
        gt = extract_ground_truth(data_roots)

        queries = []
        for item in gt:
            self.fingerprints.append(
                (item['target_org'], item['target_file'], item['query']))
            queries.append(item['query'])

        # Build a FAISS index of all possible query fingerprints
        vecs = self.model.encode(queries).astype('float32')
        faiss.normalize_L2(vecs)
        self.index = faiss.IndexFlatIP(vecs.shape[1])
        self.index.add(vecs)

    def attack(self, query_vector, target_org, target_file):
        """Returns (is_successful, top_match_score)."""
        vec = query_vector.copy().astype('float32').reshape(1, -1)
        faiss.normalize_L2(vec)
        scores, indices = self.index.search(vec, 1)
        org, fn, _ = self.fingerprints[int(indices[0][0])]
        return (org == target_org and fn == target_file), float(scores[0][0])

    def attack_top_k(self, query_vector, target_org, target_file, k=5):
        """Returns (was_in_top_k, rank_position)."""
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
    Simulates an adaptive adversary that attempts to 'denoise' VS-ADP by averaging
    multiple observations of the same logical query.
    """

    def __init__(self, template_attack, privacy_adapter, ref_node):
        self.template_attack = template_attack
        self.pa = privacy_adapter
        self.ref_node = ref_node

    def attack_with_n_observations(self, query_text, target_org, target_file, n=1):
        """
        Issue N noisy versions of the query and average them before performing
        the template fingerprinting attack.
        """
        plain_vec = self.ref_node.encode_query(query_text)
        noisy_vecs = [self.pa.add_noise_to_vector(plain_vec.copy()) for _ in range(n)]
        avg_vec = np.mean(noisy_vecs, axis=0).astype('float32')
        faiss.normalize_L2(avg_vec.reshape(1, -1))
        return self.template_attack.attack(avg_vec, target_org, target_file)


# ═══════════════════════════════════════════════════════════════════════
# CATEGORY B: Score/Transit Attacks (Target: HE-Lite)
# ═══════════════════════════════════════════════════════════════════════

class MembershipInferenceAttack:
    """
    Membership Inference Attack (MIA).
    
    Determines if a document is present in a node's local database by 
    monitoring the similarity scores returned for high-relevance queries.
    """

    def __init__(self, threshold=0.5):
        self.threshold = threshold

    def calibrate(self, member_scores, nonmember_scores):
        """Sets the optimal threshold for distinguishing members from non-members."""
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
        """Predicts membership based on the similarity score."""
        return max_score >= self.threshold


class ScoreInferenceAttack:
    """
    Builds relevance profiles by monitoring (Query, Document-Score) pairs.
    """

    def __init__(self):
        self.intercepted = []  

    def intercept(self, query_text, results, encrypted=False):
        """Record an intercepted interaction. If encrypted, no data is logged."""
        if encrypted:
            self.intercepted.append((query_text, None))
        else:
            ranked = sorted(
                [(r['org'], r['filename'], r['score']) for r in results],
                key=lambda x: x[2], reverse=True
            )
            self.intercepted.append((query_text, ranked))

    def compute_profile_accuracy(self, ground_truth):
        """Calculates the adversary's Accuracy in predicting a query's top-1 target."""
        correct, total = 0, 0
        gt_lookup = {item['query']: (item['target_org'], item['target_file'])
                     for item in ground_truth}

        for query, ranked in self.intercepted:
            if ranked is None:
                continue 
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
    A powerful score-probing attack that attempts to reconstruct a document's 
    entire embedding vector using a least-squares projection of probe query scores.
    """

    def __init__(self, embedding_dim=384, n_probes=100):
        self.d = embedding_dim
        self.n_probes = n_probes

    def attack(self, score_oracle, true_embedding=None):
        """
        Reconstructs the embedding via random projections and observes the oracle response.
        """
        # 1. Probing Phase
        probes = np.random.randn(self.n_probes, self.d).astype('float32')
        faiss.normalize_L2(probes)
        scores = np.array([score_oracle(probes[i]) for i in range(self.n_probes)])

        # 2. Reconstruction Phase (Sum-of-Projections)
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
    """Calculates the geometric divergence between two vectors (1 - cosine similarity)."""
    a = original_vec.flatten()
    b = noisy_vec.flatten()
    cos_sim = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10)
    return 1.0 - cos_sim
