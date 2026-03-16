"""
Standard Information Retrieval (IR) Evaluation Metrics for Priva-Fed.

This module provides the core metric calculations used to evaluate the 
utility-privacy trade-off. It includes standard rank-aware metrics (Recall, MRR, 
NDCG) and custom alignment metrics (Semantic Drift, Rank Correlation) to measure
perturbation divergence.
"""

import numpy as np


def compute_recall_at_k(retrieved_ids, target_id, k):
    """
    Calculates binary recall at K.
    Returns 1 if the ground-truth target is within the top-K results, else 0.
    """
    return 1 if target_id in retrieved_ids[:k] else 0


def compute_mrr(retrieved_ids, target_id):
    """
    Calculates the Mean Reciprocal Rank (MRR).
    Returns 1/rank if the target is found in the results, otherwise 0.
    """
    for rank, rid in enumerate(retrieved_ids, start=1):
        if rid == target_id:
            return 1.0 / rank
    return 0.0


def compute_ndcg_at_k(retrieved_ids, target_id, k):
    """
    Calculates Normalized Discounted Cumulative Gain (NDCG) at K.
    Assumes a single relevant document for search benchmarking.
    """
    ideal_dcg = 1.0  # Assumes target at rank 1 is the ideal case
    for rank, rid in enumerate(retrieved_ids[:k], start=1):
        if rid == target_id:
            actual_dcg = 1.0 / np.log2(rank + 1)
            return actual_dcg / ideal_dcg
    return 0.0


def compute_semantic_drift(baseline_ranking, private_ranking, k=10):
    """
    Measures the 'drift' in retrieval focus caused by privacy noise.
    Uses Jaccard-like overlap of the top-K retrieved item sets.
    
    Returns 1.0 for perfect overlap, 0.0 for total divergence.
    """
    baseline_set = set(baseline_ranking[:k])
    private_set = set(private_ranking[:k])
    
    if len(baseline_set) == 0:
        return 1.0  
    
    overlap = len(baseline_set & private_set)
    return overlap / len(baseline_set)


def compute_rank_correlation(baseline_ranking, private_ranking, k=10):
    """
    Calculates Spearman's Rank Correlation Coefficient for the top-K items.
    Measures how consistently the items are ordered between the baseline and 
    the private configuration.
    
    Returns a value in [-1, 1], where 1 represents perfect order agreement.
    """
    baseline_top = baseline_ranking[:k]
    private_top = private_ranking[:k]
    all_items = list(set(baseline_top) | set(private_top))
    
    if len(all_items) <= 1:
        return 1.0
    
    # Internal utility to assign ranks to items, handling missing values
    def get_rank(item, lst):
        try:
            return lst.index(item) + 1
        except ValueError:
            return k + 1
    
    baseline_ranks = [get_rank(item, baseline_top) for item in all_items]
    private_ranks = [get_rank(item, private_top) for item in all_items]
    
    # Spearman Rho Calculation
    n = len(all_items)
    d_sq = sum((b - p) ** 2 for b, p in zip(baseline_ranks, private_ranks))
    
    if n * (n**2 - 1) == 0:
        return 1.0
    
    rho = 1 - (6 * d_sq) / (n * (n**2 - 1))
    return rho
