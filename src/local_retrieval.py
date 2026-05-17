"""
Local Node Implementation for the Priva-Fed Federated Retrieval System.

Each `LocalNode` represents an organization's isolated data silo. It maintains its
own document collection, vector index (FAISS), and sparse index (BM25).

Core Capabilities:
1. Hybrid Retrieval: Combines dense vector search with sparse BM25 scores.
2. Cross-Encoder Re-ranking: Uses a transformer-based cross-encoder for high-precision
   reranking of the top candidates.
3. Secure Aggregation (P2P Masking): Implements a zero-sum masking protocol that allows
   the Hub to sum scores across nodes without ever seeing the raw local scores.
4. Privacy Mechanism Support: Handles local execution of HE dot products and LSH matching.
"""

import os
import time
import glob
import faiss
import numpy as np
import re
from sentence_transformers import SentenceTransformer, CrossEncoder
from rank_bm25 import BM25Okapi


class LocalNode:
    """
    Simulates a secure data silo for a participating organization in the federation.
    """
    def __init__(self, org_name, data_dir="data/synthetic",
                 model_name='all-MiniLM-L6-v2',
                 cross_encoder_name='cross-encoder/ms-marco-TinyBERT-L-2-v2'):
        """
        Args:
            org_name: Unique identifier for the organization (e.g., 'org_A').
            data_dir: Root directory for synthetic narratives.
            model_name: SentenceTransformer model used for dense embeddings.
            cross_encoder_name: Model used for secondary reranking.
        """
        self.org_name = org_name
        self.data_dir = os.path.join(data_dir, org_name)
        self.model_name = model_name
        self.cross_encoder_name = cross_encoder_name
        self.documents = []
        self.filenames = []
        self.tokenized_corpus = []
        self.embeddings = None   
        self.lsh_signatures = None 
        self.index = None
        self.bm25 = None
        self.model = None
        self.cross_encoder = None
        
        # Out-of-Band (OOB) simulated secret storage for P2P masking
        self.pairwise_secrets = {} 

    def _tokenize(self, text):
        """Standard alphanumeric tokenizer for sparse retrieval."""
        return re.findall(r'\w+', text.lower())

    def get_model(self):
        """Memory-efficient lazy loading of the embedding model."""
        if self.model is None:
            self.model = SentenceTransformer(self.model_name)
        return self.model

    def load_data(self):
        """Loads and tokenizes documents from the organization's specific data directory."""
        print(f"[{self.org_name}] Loading data from {self.data_dir}...")
        file_paths = sorted(glob.glob(os.path.join(self.data_dir, "*.txt")))
        for path in file_paths:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        self.documents.append(content)
                        self.filenames.append(os.path.basename(path))
                        self.tokenized_corpus.append(self._tokenize(content))
            except Exception as e:
                print(f"Error reading {path}: {e}")
        print(f"[{self.org_name}] Loaded {len(self.documents)} documents.")

    def build_index(self):
        """Initializes both dense (FAISS) and sparse (BM25) search indices."""
        if not self.documents:
            return
        model = self.get_model()
        print(f"[{self.org_name}] Generating dense embeddings...")
        self.embeddings = model.encode(self.documents).astype('float32')
        faiss.normalize_L2(self.embeddings)

        dimension = self.embeddings.shape[1]
        print(f"[{self.org_name}] Building FAISS index (dim={dimension})...")
        self.index = faiss.IndexFlatIP(dimension)
        self.index.add(self.embeddings)

        print(f"[{self.org_name}] Building BM25 index...")
        self.bm25 = BM25Okapi(self.tokenized_corpus)

    def encode_query(self, query_text):
        """Transforms a natural language string into a normalized unit vector."""
        model = self.get_model()
        vec = model.encode([query_text]).astype('float32')
        faiss.normalize_L2(vec)
        return vec

    def generate_p2p_mask(self, query_id, all_orgs, top_k=10):
        """
        Implements a zero-sum masking protocol. 
        Each node pair generates a shared random value; one adds it, the other subtracts it.
        Under reliable consensus, these masks cancel out at the Hub, revealing 
        the true global score sum without exposing raw local scores.
        """
        import hashlib
        mask = np.zeros(top_k)
        my_idx = all_orgs.index(self.org_name)
        
        for other_idx, other_org in enumerate(all_orgs):
            if my_idx == other_idx:
                continue
            
            # Privacy Guard: Secrets MUST be exchanged OOB
            if other_org not in self.pairwise_secrets:
                raise RuntimeError(f"[{self.org_name}] Missing pairwise secret for {other_org}. "
                                 "Secure aggregation is compromised.")
            
            shared_secret = self.pairwise_secrets[other_org]
            
            # Deterministic seed for masks based on (secret + session_id)
            seed_str = f"{shared_secret}_{query_id}".encode()
            seed = int(hashlib.sha256(seed_str).hexdigest(), 16) % (2**32)
            
            rng = np.random.default_rng(seed)
            pairwise_mask = rng.normal(0, 0.5, top_k)
            
            # Cancellation logic: node with lower index adds, higher index subtracts
            if my_idx < other_idx:
                mask += pairwise_mask
            else:
                mask -= pairwise_mask
        return mask

    def score_candidates(self, query_id, all_orgs, candidates, 
                          query_text=None, query_vector=None, pa=None, rerank=True):
        """
        Calculates relevance scores for a specific set of union candidates.
        Applies zero-sum masking before returning the results to the Hub.
        """
        if query_vector is None:
            raise ValueError("Query vector required for scoring.")
        
        results = []
        for org, filename in candidates:
            score = 0.0
            if org == self.org_name:
                try:
                    idx = self.filenames.index(filename)
                    # 1. Primary Scoring (Ciphertext-Aware)
                    if isinstance(query_vector, bytes) and pa:
                        # HE Dot Product: Encrypted Query @ Plaintext Document
                        blob, _ = pa.compute_encrypted_dot_product(query_vector, self.embeddings[idx])
                        # Benchmarking simulation decodes for assessment
                        scores, _ = pa.decrypt_scores(blob)
                        score = float(scores[0])
                    else:
                        score = float(np.dot(self.embeddings[idx], query_vector.flatten()))
                    
                    # 2. Sparse (BM25) Term Enhancement
                    if query_text and self.bm25 and not isinstance(query_vector, bytes):
                        tokenized_query = self._tokenize(query_text)
                        bm25_score = self.bm25.get_batch_scores(tokenized_query, [idx])[0]
                        score += 0.3 * (bm25_score / 20.0) 

                    # 3. SOTA Re-ranking (Cross-Encoder)
                    if rerank and query_text and self.cross_encoder:
                        ce_score = self.cross_encoder.predict([query_text, self.documents[idx]])
                        score = float(ce_score)
                        
                except Exception:
                    score = 0.0
            results.append({'org': org, 'filename': filename, 'score': score})

        # Apply P2P Identity Hiding Masks
        mask = self.generate_p2p_mask(query_id, all_orgs, top_k=len(results))
        for i, r in enumerate(results):
            r['score'] += float(mask[i])
            
        return results

    def search(self, query, k=5, rerank=True, query_vector=None, pa=None):
        """
        Performs the local first-pass retrieval (Pass 1).
        Uses Hybrid RRF (Dense + Sparse) and returns candidate descriptors.
        """
        if self.index is None or self.bm25 is None:
            raise ValueError("Indices not built.")

        if rerank and self.cross_encoder is None:
            try:
                self.cross_encoder = CrossEncoder(self.cross_encoder_name)
            except Exception:
                rerank = False

        t0 = time.time()

        # Sparse Pass
        tokenized_query = self._tokenize(query)
        bm25_scores = self.bm25.get_scores(tokenized_query)
        bm25_top = np.argsort(bm25_scores)[::-1][:100]

        # Dense Pass (Mechanism-Specific)
        is_encrypted = isinstance(query_vector, bytes)
        if is_encrypted and pa:
            # Encrypted retrieval simulation (HE bottlenecked)
            candidates = bm25_top[:10] 
            ce_scored_indices = []
            for idx in candidates:
                blob, _ = pa.compute_encrypted_dot_product(query_vector, self.embeddings[idx])
                score, _ = pa.decrypt_scores(blob)
                ce_scored_indices.append((idx, score[0]))
            
            ce_scored_indices.sort(key=lambda x: x[1], reverse=True)
            dense_indices = np.array([[x[0] for x in ce_scored_indices]])
        elif pa and pa.mode in ('lsh', 'lsh_adp'):
            # SimHash similarity lookup
            if self.lsh_signatures is None:
                self.lsh_signatures = pa.compute_lsh(self.embeddings)
            
            q_hash = pa.compute_lsh(query_vector)
            lsh_scores = np.array([pa.hamming_similarity(q_hash, doc_h) for doc_h in self.lsh_signatures])
            dense_top = np.argsort(lsh_scores)[::-1][:100]
            dense_indices = np.array([dense_top])
        else:
            if query_vector is None:
                query_vector = self.encode_query(query)
            _, dense_indices = self.index.search(query_vector, 100)

        # Reciprocal Rank Fusion (Standardized Utility Merging)
        rrf = {}
        K_RRF = 60
        for rank, idx in enumerate(dense_indices[0]):
            if idx != -1:
                rrf[idx] = rrf.get(idx, 0.0) + 1.0 / (K_RRF + rank + 1)
        for rank, idx in enumerate(bm25_top):
            if bm25_scores[idx] > 0:
                rrf[idx] = rrf.get(idx, 0.0) + 1.0 / (K_RRF + rank + 1)

        k_rerank = min(20, len(rrf))
        top_indices = sorted(rrf, key=rrf.get, reverse=True)[:k_rerank]

        # Final Local Re-ranking
        if rerank and self.cross_encoder and len(top_indices) > 0:
            pairs = [[query, self.documents[idx]] for idx in top_indices]
            ce_scores = self.cross_encoder.predict(pairs)
            scored = sorted(zip(top_indices, ce_scores),
                            key=lambda x: x[1], reverse=True)[:k]
            results = [
                {'org': self.org_name, 'filename': self.filenames[idx],
                 'content': self.documents[idx], 'score': float(sc)}
                for idx, sc in scored
            ]
        else:
            top_k_idx = top_indices[:k]
            results = [
                {'org': self.org_name, 'filename': self.filenames[idx],
                 'content': self.documents[idx], 'score': rrf[idx]}
                for idx in top_k_idx
            ]

        latency = (time.time() - t0) * 1000
        return results, latency
