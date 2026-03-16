"""
Centralized Hub Orchestration for the Priva-Fed Retrieval System.

The `HubOrchestrator` is responsible for coordinating the multi-pass retrieval 
protocol between the client (central Hub) and the decentralized Local Nodes (Organizations).

Key Features:
1. Multi-Pass Protocol:
   - PASS 1: Candidate Gathering (Broad search across nodes).
   - PASS 2: Secure Aggregation (Masked scoring/summing to prevent score interception).
   - PASS 3: Content Retrieval (Fetching raw text ONLY for the final top-K results).
2. Privacy Enforcement:
   - Integrates with the `PrivacyAdapter` to apply VS-ADP, HE-Lite, or LSH.
   - Enforce privacy budget limits via the `PrivacyAccountant`.
3. K-Anonymity:
   - Supports chaff query generation to provide k-anonymity for the query text itself.
"""

import time
import numpy as np
from operator import itemgetter
from collections import defaultdict


class HubOrchestrator:
    """
    Coordinates the federated retrieval process while enforcing privacy constraints.
    """
    def __init__(self, nodes, privacy_adapter=None, enforce_budget=True, k_anonymity=1):
        """
        Args:
            nodes: List of LocalNode instances.
            privacy_adapter: An instance of PrivacyAdapter.
            enforce_budget: Whether to stop querying if the epsilon budget is exceeded.
            k_anonymity: Total number of queries sent (real + k-1 chaff) to obscure the user's intent.
        """
        self.nodes = nodes
        self.pa = privacy_adapter
        self.enforce_budget = enforce_budget
        self.k_anonymity = k_anonymity
        self.stats = {}

    def _generate_chaff_query(self):
        """Generates a plausible-looking 'fake' query to satisfy k-anonymity requirements."""
        entities = ["user 123", "account XJ9", "transaction REF-44", "customer ID 99"]
        actions = ["details for", "history of", "summarize", "check status of"]
        q = f"{np.random.choice(actions)} {np.random.choice(entities)}"
        return q

    def _reset(self):
        """Initialize performance and bandwidth statistics for a new query broadcast."""
        self.stats = {
            'total_latency_ms': 0, 'search_latency_ms': 0,
            'privacy_latency_ms': 0, 'bandwidth_bytes': 0,
        }

    def broadcast(self, query_text, top_k=10):
        """
        Executes the three-pass federated retrieval protocol.
        
        Args:
            query_text: The user's natural language query.
            top_k: Number of relevant results to return.
            
        Returns:
            - results: List of {org, filename, content, score}
            - stats: Dictionary of performance metrics.
            - raw_scores: Pass 2 results (used for adversarial evaluation).
        """
        t0 = time.time()
        self._reset()
        mode = self.pa.mode if self.pa else 'plaintext'
        uses_noise = mode in ('vs_adp', 'combined')
        uses_he = mode in ('he_lite', 'combined')

        # 1. Budget Verification
        if self.pa and uses_noise:
            eps, limit, exhausted = self.pa.get_budget_status()
            if exhausted and self.enforce_budget:
                return [], self.stats, {}

        # 2. Query Preparation
        queries = [query_text]
        for _ in range(self.k_anonymity - 1):
            queries.append(self._generate_chaff_query())

        all_real_candidates = []
        raw_scores_log = {}

        # Secure Aggregation Context (Query-specific session ID)
        all_orgs = [n.org_name for n in self.nodes]
        query_id = f"{query_text}_{time.time()}"

        for q_idx, q_text in enumerate(queries):
            is_real = (q_idx == 0)
            ref = self.nodes[0]
            plain_vec = ref.encode_query(q_text)
            
            # Apply Vector-Space Noise
            if uses_noise:
                query_vec = self.pa.add_noise_to_vector(plain_vec.copy())
            else:
                query_vec = plain_vec

            # Encryption for Bandwidth/Score Protection
            if uses_he:
                query_vec, plat = self.pa.encrypt_vector(query_vec)
                self.stats['privacy_latency_ms'] += plat

            # --- PASS 1: Candidate Gathering ---
            candidates_union = []
            for node in self.nodes:
                # Local nodes search their indices and return top candidate descriptors
                res, slat = node.search(q_text, k=top_k, rerank=True, query_vector=query_vec, pa=self.pa)
                self.stats['search_latency_ms'] += slat
                for r in res:
                    candidates_union.append((r['org'], r['filename']))
                    if is_real:
                        # Log Pass 1 metadata (for MIA analysis)
                        r_meta = {k: v for k, v in r.items() if k != 'content'}
                        raw_scores_log.setdefault(node.org_name, []).append(r_meta)

            # --- PASS 2: Secure Aggregation (Score Summing) ---
            # Remove duplicate descriptors to form the union candidate set
            unique_candidates = list(dict.fromkeys(candidates_union))
            
            # Nodes calculate scores for the union set using P2P Masking
            global_scores = defaultdict(float)
            for node in self.nodes:
                masked_results = node.score_candidates(query_id, all_orgs, 
                                                       unique_candidates, 
                                                       query_vector=query_vec,
                                                       query_text=q_text,
                                                       pa=self.pa)
                for r in masked_results:
                    # Hub sums masked scores; masks cancel out if all nodes respond
                    global_scores[(r['org'], r['filename'])] += r['score']

            if is_real:
                # 3. Pass 2 Ranking & Pass 3 Content Fetching
                results = []
                node_map = {n.org_name: n for n in self.nodes}

                for (org, fname), score in global_scores.items():
                    results.append({'org': org, 'filename': fname, 'score': score})
                
                results.sort(key=itemgetter('score'), reverse=True)
                final_top_k = results[:top_k]
                
                # PASS 3: Request raw content ONLY for finalized top-k
                for r_final in final_top_k:
                    n = node_map.get(r_final['org'])
                    if n:
                        try:
                            idx = n.filenames.index(r_final['filename'])
                            r_final['content'] = n.documents[idx]
                        except ValueError:
                            r_final['content'] = "[REDACTED]"
                    else:
                        r_final['content'] = "[REDACTED]"
                
                all_real_candidates = final_top_k

            # Real-world Bandwidth Estimation
            if isinstance(query_vec, bytes):
                q_size = len(query_vec)
                # Encrypted scalar blob overhead for each candidate
                r_size = 235375 * len(unique_candidates) 
            else:
                q_size = query_vec.nbytes if hasattr(query_vec, 'nbytes') else len(str(query_vec).encode())
                r_size = 32 * len(unique_candidates) 
            
            self.stats['bandwidth_bytes'] += (q_size + r_size) * len(self.nodes)

        all_real_candidates.sort(key=itemgetter('score'), reverse=True)
        self.stats['total_latency_ms'] = (time.time() - t0) * 1000
        
        # Structure the global_scores list for adversarial assessment
        aggregated_scores = []
        if 'global_scores' in locals():
            for (org, fname), score in global_scores.items():
                aggregated_scores.append({'org': org, 'filename': fname, 'score': score})

        return all_real_candidates[:top_k], self.stats, aggregated_scores
