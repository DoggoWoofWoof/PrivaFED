"""
Privacy mechanisms for Priva-Fed.

Uses dimensionality-aware Gaussian noise calibration.

The noise_scale parameter controls the noise-to-signal ratio (NSR):
   noise_L2 / embedding_L2 = noise_scale

For a d-dimensional unit vector, per-dimension sigma = noise_scale / sqrt(d).

This ensures the noise is proportional to the signal regardless of
dimensionality (d=384 for all-MiniLM-L6-v2).
"""

import numpy as np
import tenseal as ts
import faiss
import time


class PrivacyAdapter:
    """
    Privacy adapter with two mechanisms:
    
    VS-ADP:  Gaussian noise on query embeddings (dimensionality-aware).
    HE-Lite: CKKS encryption of similarity scores.
    """

    def __init__(self, mode='plaintext', noise_scale=0.0):
        """
        Args:
            mode: 'plaintext', 'vs_adp', 'he_lite', or 'combined'
            noise_scale: Target noise-to-signal L2 ratio (for vs_adp/combined).
                         0.0 = no noise, 1.0 = noise L2 equals signal L2.
        """
        self.mode = mode
        self.noise_scale = noise_scale
        self.he_ctx = None

        if self.mode in ('he_lite', 'combined'):
            self._init_he()

    # ────────────────────────────── HE Context ──────────────────────────
    def _init_he(self):
        self.he_ctx = ts.context(
            ts.SCHEME_TYPE.CKKS,
            poly_modulus_degree=8192,
            coeff_mod_bit_sizes=[60, 40, 40, 60],
        )
        self.he_ctx.global_scale = 2**40
        self.he_ctx.generate_galois_keys()

    def encrypt_scores(self, scores):
        t0 = time.time()
        ct = ts.ckks_vector(self.he_ctx, scores)
        blob = ct.serialize()
        return blob, (time.time() - t0) * 1000

    def decrypt_scores(self, blob):
        t0 = time.time()
        ct = ts.ckks_vector_from(self.he_ctx, blob)
        scores = ct.decrypt()
        return scores, (time.time() - t0) * 1000

    # ────────────────────────── Gaussian Noise ──────────────────────────
    def add_noise_to_vector(self, query_vector):
        """
        Add dimensionality-aware Gaussian noise.
        
        Per-dim sigma = noise_scale / sqrt(d), so total noise L2 ~ noise_scale.
        Vector is re-normalised to unit sphere after perturbation.
        """
        d = query_vector.shape[-1]
        sigma_per_dim = self.noise_scale / np.sqrt(d)
        noise = np.random.normal(0, sigma_per_dim, query_vector.shape).astype('float32')
        noisy = query_vector + noise
        faiss.normalize_L2(noisy.reshape(-1, d))
        return noisy

    def redact_content(self, results):
        for r in results:
            r['content'] = "[REDACTED]"
        return results
