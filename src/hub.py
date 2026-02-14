"""
Hub Orchestrator for Priva-Fed.

Supports 4 privacy modes:
  plaintext:  No protection
  vs_adp:     Gaussian noise on query vector (defends against query attacks)
  he_lite:    CKKS encryption on scores in transit (defends against score attacks)
  combined:   VS-ADP noise + HE encryption (defends against both)

All modes: Hub encodes query once, passes vector to all nodes.
"""

import time
from operator import itemgetter


class HubOrchestrator:
    def __init__(self, nodes, privacy_adapter=None):
        self.nodes = nodes
        self.pa = privacy_adapter
        self.stats = {}

    def _reset(self):
        self.stats = {
            'total_latency_ms': 0, 'search_latency_ms': 0,
            'privacy_latency_ms': 0, 'bandwidth_bytes': 0,
        }

    def broadcast(self, query_text, top_k=10):
        t0 = time.time()
        self._reset()
        mode = self.pa.mode if self.pa else 'plaintext'
        uses_noise = mode in ('vs_adp', 'combined')
        uses_he = mode in ('he_lite', 'combined')

        # Encode query once
        ref = self.nodes[0]
        plain_vec = ref.encode_query(query_text)

        # Apply noise if needed
        if uses_noise:
            tp = time.time()
            query_vec = self.pa.add_noise_to_vector(plain_vec.copy())
            self.stats['privacy_latency_ms'] += (time.time() - tp) * 1000
        else:
            query_vec = plain_vec

        all_results = []
        raw_scores_per_node = {}  # For score attack evaluation

        for node in self.nodes:
            res, slat = node.search(query_text, k=top_k,
                                    rerank=True, query_vector=query_vec)
            self.stats['search_latency_ms'] += slat

            # Store raw scores before any encryption (for attack evaluation)
            raw_scores_per_node[node.org_name] = [
                {'org': r['org'], 'filename': r['filename'], 'score': r['score']}
                for r in res
            ]

            if uses_he:
                scores = [r['score'] for r in res]
                blob, enc_ms = self.pa.encrypt_scores(scores)
                self.stats['privacy_latency_ms'] += enc_ms
                self.stats['bandwidth_bytes'] += len(blob)
                dec_scores, dec_ms = self.pa.decrypt_scores(blob)
                self.stats['privacy_latency_ms'] += dec_ms
                for i, r in enumerate(res):
                    r['score'] = float(dec_scores[i])

            # Consistent bandwidth: metadata per result
            for r in res:
                payload = str({'org': r['org'], 'filename': r['filename'],
                               'score': r['score']})
                self.stats['bandwidth_bytes'] += len(payload.encode('utf-8'))

            # Content never leaves node
            for r in res:
                r['content'] = "[REDACTED]"

            all_results.extend(res)

        all_results.sort(key=itemgetter('score'), reverse=True)
        self.stats['total_latency_ms'] = (time.time() - t0) * 1000
        return all_results[:top_k], self.stats, raw_scores_per_node
