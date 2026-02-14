"""
Standard IR evaluation metrics for Priva-Fed benchmarking.
"""
import numpy as np


def compute_recall_at_k(retrieved_ids, target_id, k):
    """Binary recall: is the target in the top-k retrieved?"""
    return 1 if target_id in retrieved_ids[:k] else 0


def compute_mrr(retrieved_ids, target_id):
    """
    Mean Reciprocal Rank.
    Returns 1/rank if target is found, else 0.
    """
    for rank, rid in enumerate(retrieved_ids, start=1):
        if rid == target_id:
            return 1.0 / rank
    return 0.0


def compute_ndcg_at_k(retrieved_ids, target_id, k):
    """
    NDCG@k for a single relevant document.
    Ideal DCG = 1/log2(2) = 1.0 (target at rank 1).
    Actual DCG = 1/log2(rank+1) if target found in top-k, else 0.
    """
    ideal_dcg = 1.0  # 1/log2(2)
    for rank, rid in enumerate(retrieved_ids[:k], start=1):
        if rid == target_id:
            actual_dcg = 1.0 / np.log2(rank + 1)
            return actual_dcg / ideal_dcg
    return 0.0


def compute_semantic_drift(baseline_ranking, private_ranking, k=10):
    """
    Measures how much the ranking changed due to privacy.
    Uses Kendall-tau-like overlap: fraction of top-k baseline docs
    that appear in top-k private results.
    
    Returns a score in [0, 1] where 1 = identical rankings, 0 = no overlap.
    """
    baseline_set = set(baseline_ranking[:k])
    private_set = set(private_ranking[:k])
    
    if len(baseline_set) == 0:
        return 1.0  # No baseline, no drift
    
    overlap = len(baseline_set & private_set)
    return overlap / len(baseline_set)


def compute_rank_correlation(baseline_ranking, private_ranking, k=10):
    """
    Spearman-like rank correlation for the top-k items.
    Maps each item to its rank in both lists and computes correlation.
    Returns value in [-1, 1] where 1 = perfect agreement.
    """
    # Get the union of items in top-k of both lists
    baseline_top = baseline_ranking[:k]
    private_top = private_ranking[:k]
    all_items = list(set(baseline_top) | set(private_top))
    
    if len(all_items) <= 1:
        return 1.0
    
    # Assign ranks (items not in a list get rank k+1)
    def get_rank(item, lst):
        try:
            return lst.index(item) + 1
        except ValueError:
            return k + 1
    
    baseline_ranks = [get_rank(item, baseline_top) for item in all_items]
    private_ranks = [get_rank(item, private_top) for item in all_items]
    
    # Spearman correlation
    n = len(all_items)
    d_sq = sum((b - p) ** 2 for b, p in zip(baseline_ranks, private_ranks))
    
    if n * (n**2 - 1) == 0:
        return 1.0
    
    rho = 1 - (6 * d_sq) / (n * (n**2 - 1))
    return rho
