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
    Represents an organization's local silo with its own search index.
    Supports Hybrid Retrieval (Dense + Sparse/BM25) + Cross-Encoder Re-ranking.
    """
    def __init__(self, org_name, data_dir="data/synthetic",
                 model_name='all-MiniLM-L6-v2',
                 cross_encoder_name='cross-encoder/ms-marco-TinyBERT-L-2-v2'):
        self.org_name = org_name
        self.data_dir = os.path.join(data_dir, org_name)
        self.model_name = model_name
        self.cross_encoder_name = cross_encoder_name
        self.documents = []
        self.filenames = []
        self.tokenized_corpus = []
        self.embeddings = None   # Store raw embeddings for attack sim
        self.index = None
        self.bm25 = None
        self.model = None
        self.cross_encoder = None

    def _tokenize(self, text):
        return re.findall(r'\w+', text.lower())

    def get_model(self):
        """Lazy-load and return the SentenceTransformer model."""
        if self.model is None:
            self.model = SentenceTransformer(self.model_name)
        return self.model

    def load_data(self):
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
        print(f"[{self.org_name}] Indices built ({self.index.ntotal} vectors).")

    def encode_query(self, query_text):
        """Encode a query string into a normalized vector."""
        model = self.get_model()
        vec = model.encode([query_text]).astype('float32')
        faiss.normalize_L2(vec)
        return vec

    def search(self, query, k=5, rerank=True, query_vector=None):
        """
        Hybrid Search (RRF) -> optional Cross-Encoder Re-ranking.
        
        If query_vector is provided, it is used for dense search directly
        (this is how VS-ADP injects noise: Hub sends noisy vector).
        BM25 search always uses the plaintext query string (BM25 operates
        on tokens, not embeddings, so it is unaffected by embedding noise).
        
        All results are tagged with self.org_name.
        """
        if self.index is None or self.bm25 is None:
            raise ValueError("Indices not built.")

        if rerank and self.cross_encoder is None:
            try:
                self.cross_encoder = CrossEncoder(self.cross_encoder_name)
            except Exception:
                rerank = False

        t0 = time.time()

        # --- Dense Search ---
        if query_vector is None:
            query_vector = self.encode_query(query)
        dense_scores, dense_indices = self.index.search(query_vector, 100)

        # --- Sparse Search (always on plaintext query) ---
        tokenized_query = self._tokenize(query)
        bm25_scores = self.bm25.get_scores(tokenized_query)
        bm25_top = np.argsort(bm25_scores)[::-1][:100]

        # --- Reciprocal Rank Fusion ---
        rrf = {}
        K_RRF = 60
        for rank, idx in enumerate(dense_indices[0]):
            if idx != -1:
                rrf[idx] = rrf.get(idx, 0.0) + 1.0 / (K_RRF + rank + 1)
        for rank, idx in enumerate(bm25_top):
            if bm25_scores[idx] > 0:
                rrf[idx] = rrf.get(idx, 0.0) + 1.0 / (K_RRF + rank + 1)

        k_rerank = min(20, len(rrf))
        candidates = sorted(rrf, key=rrf.get, reverse=True)[:k_rerank]

        # --- Cross-Encoder Re-ranking ---
        if rerank and self.cross_encoder and len(candidates) > 0:
            pairs = [[query, self.documents[idx]] for idx in candidates]
            ce_scores = self.cross_encoder.predict(pairs)
            scored = sorted(zip(candidates, ce_scores),
                            key=lambda x: x[1], reverse=True)[:k]
            results = [
                {
                    'org': self.org_name,
                    'filename': self.filenames[idx],
                    'content': self.documents[idx],
                    'score': float(sc),
                }
                for idx, sc in scored
            ]
        else:
            top_k = candidates[:k]
            results = [
                {
                    'org': self.org_name,
                    'filename': self.filenames[idx],
                    'content': self.documents[idx],
                    'score': rrf[idx],
                }
                for idx in top_k
            ]

        latency = (time.time() - t0) * 1000
        return results, latency
