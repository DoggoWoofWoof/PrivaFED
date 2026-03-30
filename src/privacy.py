"""
Privacy mechanisms for the Priva-Fed system.

This module implements the three core privacy-preserving adapters investigated in the
workshop paper:

1. VS-ADP (Vector-Space Approximate Differential Privacy): 
   Adds dimensionality-aware Gaussian noise to query embeddings. The noise is 
   calibrated such that the noise-to-signal ratio (LSR) is constant regardless of 
   embedding dimensionality (d=384 for all-MiniLM-L6-v2).
   
2. HE-Lite (Homomorphic Encryption): 
   Uses the CKKS scheme (via TenSEAL) to encrypt relevance scores. This prevents 
   the Hub from observing raw similarity scores, thus blocking score-based attacks.

3. LSH (Locality Sensitive Hashing): 
   Maps embeddings to 64-bit binary signatures (SimHash) as a lightweight, non-cryptographic
   alternative for score protection.

The module also includes a `PrivacyAccountant` to track Cumulative Privacy Budget 
consumption using Rényi Differential Privacy (RDP).
"""

import numpy as np
import tenseal as ts
import faiss
import time


class PrivacyAccountant:
    """
    Tracks Differential Privacy (DP) budget consumption using Rényi Differential Privacy (RDP).
    
    RDP provides a tighter composition bound across multiple queries compared to 
    standard (epsilon, delta) DP. For a Gaussian mechanism with noise sigma, 
    RDP at order alpha is calculated as:
    
    epsilon(alpha) = alpha / (2 * sigma^2)
    """
    def __init__(self, target_delta=1e-5):
        """
        Args:
            target_delta: The 'delta' parameter for the converted (epsilon, delta) guarantee.
        """
        self.target_delta = target_delta
        self.rdp_history = []  # List of RDP epsilon arrays (one per query)
        self.alphas = np.linspace(1.1, 20, 20)  # Standard alpha sweep for RDP conversion

    def accumulate_query(self, sigma, multi_pass=True):
        """
        Record the privacy cost of a single query interaction.
        
        Args:
            sigma: Standard deviation of the Gaussian noise applied.
            multi_pass: Whether the query involves multiple passes (e.g., candidate selection + refinement).
        """
        # Sensitivity Delta f = 2.0 (maximal change in dot product similarity between unit vectors)
        sensitivity = 2.0
        passes = 2 if multi_pass else 1
        
        # Calculate RDP epsilon for this query at all tracked alphas
        rdp_eps = passes * (self.alphas * (sensitivity**2)) / (2 * (sigma**2))
        self.rdp_history.append(rdp_eps)

    def get_total_epsilon(self):
        """
        Convert accumulated RDP history into a single 'epsilon' value at target_delta.
        
        Returns:
            The minimum epsilon across all alpha candidates.
        """
        if not self.rdp_history:
            return 0.0
        
        # Sum RDP epsilons across queries (linear composition in RDP space)
        total_rdp = np.sum(self.rdp_history, axis=0)
        
        # Convert RDP to standard epsilon: eps = total_rdp + log(1/delta) / (alpha - 1)
        eps_candidates = total_rdp + np.log(1 / self.target_delta) / (self.alphas - 1)
        return float(np.min(eps_candidates))


class PrivacyAdapter:
    """
    The central interface for applying privacy transformations to the retrieval pipeline.
    
    Supports VS-ADP noise, HE score encryption, LSH binary hashing,
    LSH+ADP, and 'combined' mode.
    """

    def __init__(self, mode='plaintext', noise_scale=0.0, lsh_bits=64,
                 epsilon_limit=10.0, delta=1e-5):
        """
        Args:
            mode: Mechanism to use ('plaintext', 'vs_adp', 'he_lite',
                'lsh', 'lsh_adp', 'combined').
            noise_scale: Target noise-to-signal L2 ratio (standardized to 384-dim signal).
            lsh_bits: Signature length for semantic hashing.
            epsilon_limit: Max privacy budget allowed before the system halts.
            delta: Probability of privacy guarantee failure (usually 1e-5).
        """
        self.mode = mode
        self.noise_scale = noise_scale
        self.lsh_bits = lsh_bits
        self.epsilon_limit = epsilon_limit
        self.he_ctx = None
        self.lsh_projections = None
        self.accountant = PrivacyAccountant(target_delta=delta)

        if self.mode in ('he_lite', 'combined'):
            self._init_he()
        
        if self.mode in ('lsh', 'lsh_adp'):
            self._init_lsh()

    def get_budget_status(self):
        """Returns (current_epsilon, limit, is_exhausted)."""
        eps = self.accountant.get_total_epsilon()
        return eps, self.epsilon_limit, eps > self.epsilon_limit

    # ────────────────────────────── HE Context ──────────────────────────
    def _init_he(self):
        """Initialize CKKS context for Secure Aggregation of scores."""
        # Using standard 8192-degree polynomial for reliable security/performance balance
        self.he_ctx = ts.context(
            ts.SCHEME_TYPE.CKKS,
            poly_modulus_degree=8192,
            coeff_mod_bit_sizes=[60, 40, 40, 60],
        )
        self.he_ctx.global_scale = 2**40
        self.he_ctx.generate_galois_keys()
        self.he_ctx.generate_relin_keys()

    def encrypt_scores(self, scores):
        """Encrypt a list of relevance scores into a serialized CKKS blob."""
        t0 = time.time()
        ct = ts.ckks_vector(self.he_ctx, scores)
        blob = ct.serialize()
        return blob, (time.time() - t0) * 1000

    def encrypt_vector(self, vector):
        """Encrypt a high-dimensional query embedding."""
        t0 = time.time()
        vec = vector.flatten().tolist()
        ct = ts.ckks_vector(self.he_ctx, vec)
        blob = ct.serialize()
        return blob, (time.time() - t0) * 1000

    def decrypt_scores(self, blob):
        """Decrypt a serialized CKKS blob back into plaintext scores."""
        t0 = time.time()
        ct = ts.ckks_vector_from(self.he_ctx, blob)
        scores = ct.decrypt()
        return scores, (time.time() - t0) * 1000

    def compute_encrypted_dot_product(self, encrypted_vec_blob, plaintext_vector):
        """
        Compute an encrypted dot product (Inner Product) between an encrypted query
        and a plaintext document embedding.
        """
        t0 = time.time()
        ct_vec = ts.ckks_vector_from(self.he_ctx, encrypted_vec_blob)
        # Inner product computed in the encrypted domain
        res_ct = ct_vec.dot(plaintext_vector.flatten().tolist())
        blob = res_ct.serialize()
        return blob, (time.time() - t0) * 1000

    # ────────────────────────── Gaussian Noise ──────────────────────────
    def add_noise_to_vector(self, query_vector, account=True):
        """
        Apply dimensionality-aware Gaussian noise to a query vector.
        
        The standard deviation is scaled by sqrt(dim) to ensure the L2 norm
        of the added noise is proportional to the target 'noise_scale'.
        """
        d = query_vector.shape[-1]
        sigma_per_dim = self.noise_scale / np.sqrt(d)
        
        # Log to accountant if budget tracking is enabled
        if account and self.mode in ('vs_adp', 'lsh_adp', 'combined'):
            self.accountant.accumulate_query(sigma_per_dim)

        noise = np.random.normal(0, sigma_per_dim, query_vector.shape).astype('float32')
        noisy = query_vector + noise
        
        # Re-normalize to unit hypersphere to maintain embedding geometric properties
        faiss.normalize_L2(noisy.reshape(-1, d))
        return noisy

    # ────────────────────────── Semantic Hashing (LSH) ──────────────────
    def _init_lsh(self, dim=384):
        """Initialize fixed random projections for Locality Sensitive Hashing."""
        np.random.seed(42)  # Shared seed ensures projection consistency across nodes
        self.lsh_projections = np.random.randn(dim, self.lsh_bits).astype('float32')

    def compute_lsh(self, vector):
        """Generate a binary SimHash signature for an embedding."""
        if self.lsh_projections is None:
            self._init_lsh(dim=vector.shape[-1])
        
        projections = np.dot(vector, self.lsh_projections)
        binary_hash = (projections > 0).astype(int)
        return binary_hash

    def hamming_similarity(self, h1, h2):
        """Approximate cosine similarity using Hamming distance of binary hashes."""
        distance = np.sum(h1 != h2)
        return 1.0 - (distance / self.lsh_bits)

    def redact_content(self, results):
        """Utility to strip raw content from results for final Hub-to-Client transmission."""
        for r in results:
            r['content'] = "[REDACTED]"
        return results
