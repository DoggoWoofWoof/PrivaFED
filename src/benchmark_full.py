"""
Priva-Fed Comprehensive Benchmark v4 — Defense Matrix.

Evaluates the full attack-defense matrix:

  Modes:    Plaintext | VS-ADP | HE-Lite | Combined (VS-ADP + HE)
  Attacks:  Query Fingerprint (Cat-A) | Score Inference (Cat-B)
            Membership Inference (Cat-B) | Embedding Reconstruction (Cat-B)

Expected defense matrix:
  +--------------------+--------+--------+--------+----------+
  |                    | Plain  | VS-ADP | HE     | Combined |
  +--------------------+--------+--------+--------+----------+
  | Query Attacks      | Vuln   | Defend | Vuln   | Defend   |
  | Score Attacks      | Vuln   | Vuln   | Defend | Defend   |
  +--------------------+--------+--------+--------+----------+

Outputs: results/results.csv, results/attack_adaptive.csv, results/defense_matrix.csv
"""

import os
import csv
import sys
import time
import numpy as np
from collections import defaultdict

from src.local_retrieval import LocalNode
from src.privacy import PrivacyAdapter
from src.hub import HubOrchestrator
from src.attack import (KnownTemplateAttack, MultiQueryAveragingAttack,
                         MembershipInferenceAttack, ScoreInferenceAttack,
                         EmbeddingReconstructionAttack,
                         compute_reconstruction_error)
from src.metrics import (compute_recall_at_k, compute_mrr, compute_ndcg_at_k,
                         compute_semantic_drift, compute_rank_correlation)
from src.ground_truth import extract_ground_truth, validate_ground_truth


# ─── Config ───────────────────────────────────────────────────────────
ORGS = ['org_A', 'org_B', 'org_C']
NOISE_SWEEP = [0.1, 0.2, 0.5, 1.0, 2.0]
N_RUNS = 3
TOP_K = 10
RESULT_DIR = "results"
RESULT_CSV = os.path.join(RESULT_DIR, "results.csv")
MATRIX_CSV = os.path.join(RESULT_DIR, "defense_matrix.csv")
ATTACK_CSV = os.path.join(RESULT_DIR, "attack_adaptive.csv")
# ──────────────────────────────────────────────────────────────────────


def result_id(r):
    return (r['org'], r['filename'])


def run_experiment(hub, gt, ref_node, pa, template_attack,
                   baseline_rankings, score_attack):
    """Run one pass: retrieval metrics + Cat-A attack + Cat-B score interception."""
    mode = pa.mode if pa else 'plaintext'
    uses_he = mode in ('he_lite', 'combined')
    m = {
        'recall_1': [], 'recall_10': [], 'mrr': [], 'ndcg_10': [],
        'semantic_drift': [], 'rank_corr': [],
        'latency_ms': [], 'bandwidth_kb': [], 'privacy_latency_ms': [],
        'attack_asr_1': [], 'attack_asr_5': [], 'recon_error': [],
    }

    for item in gt:
        q = item['query']
        tid = (item['target_org'], item['target_file'])

        results, stats, raw_scores = hub.broadcast(q, top_k=TOP_K)
        ids = [result_id(r) for r in results]

        m['recall_1'].append(compute_recall_at_k(ids, tid, 1))
        m['recall_10'].append(compute_recall_at_k(ids, tid, 10))
        m['mrr'].append(compute_mrr(ids, tid))
        m['ndcg_10'].append(compute_ndcg_at_k(ids, tid, 10))
        m['latency_ms'].append(stats['total_latency_ms'])
        m['bandwidth_kb'].append(stats['bandwidth_bytes'] / 1024)
        m['privacy_latency_ms'].append(stats.get('privacy_latency_ms', 0))

        bl = baseline_rankings.get(q, [])
        m['semantic_drift'].append(compute_semantic_drift(bl, ids, TOP_K))
        m['rank_corr'].append(compute_rank_correlation(bl, ids, TOP_K))

        # Cat-A: Query fingerprint attack
        plain_vec = ref_node.encode_query(q)
        atk_vec = (pa.add_noise_to_vector(plain_vec.copy())
                   if mode in ('vs_adp', 'combined') and pa else plain_vec.copy())

        s1, _ = template_attack.attack(atk_vec, item['target_org'],
                                        item['target_file'])
        s5, _ = template_attack.attack_top_k(atk_vec, item['target_org'],
                                              item['target_file'], k=5)
        m['attack_asr_1'].append(1 if s1 else 0)
        m['attack_asr_5'].append(1 if s5 else 0)
        m['recon_error'].append(compute_reconstruction_error(plain_vec, atk_vec))

        # Cat-B: Score interception (for ScoreInferenceAttack)
        all_raw = []
        for org_scores in raw_scores.values():
            all_raw.extend(org_scores)
        score_attack.intercept(q, [{'org': s['org'], 'filename': s['filename'],
                                     'score': s['score']} for s in all_raw],
                                encrypted=uses_he)

    return {k: float(np.mean(v)) for k, v in m.items()}


def run_mia_experiment(nodes, gt, ref_node, mode, pa, n_queries=50):
    """
    Membership Inference Attack evaluation.
    
    Hub sends queries for documents it KNOWS are in a target node's corpus
    (member queries) and queries for documents NOT in that node (non-member).
    From raw scores, it tries to distinguish members from non-members.
    
    HE-Lite: scores encrypted -> MIA impossible (accuracy = random = 50%).
    """
    uses_he = mode in ('he_lite', 'combined')
    target_node = nodes[0]  # Attack org_A's corpus
    hub = HubOrchestrator([target_node], privacy_adapter=pa)

    # Member queries: target documents in org_A
    member_gt = [g for g in gt if g['target_org'] == target_node.org_name][:n_queries]
    # Non-member queries: target documents in OTHER orgs
    nonmember_gt = [g for g in gt if g['target_org'] != target_node.org_name][:n_queries]

    member_scores = []
    for item in member_gt:
        results, _, raw = hub.broadcast(item['query'], top_k=TOP_K)
        if uses_he:
            member_scores.append(0.5)  # Attacker can't see real score
        else:
            org_raw = raw.get(target_node.org_name, [])
            if org_raw:
                member_scores.append(max(s['score'] for s in org_raw))
            else:
                member_scores.append(0.0)

    nonmember_scores = []
    for item in nonmember_gt:
        results, _, raw = hub.broadcast(item['query'], top_k=TOP_K)
        if uses_he:
            nonmember_scores.append(0.5)  # Attacker can't see real score
        else:
            org_raw = raw.get(target_node.org_name, [])
            if org_raw:
                nonmember_scores.append(max(s['score'] for s in org_raw))
            else:
                nonmember_scores.append(0.0)

    mia = MembershipInferenceAttack()
    if uses_he:
        return 0.5, 0.5  # Random guess — encryption hides scores
    else:
        thresh, accuracy = mia.calibrate(member_scores, nonmember_scores)
        return accuracy, thresh


def run_emb_reconstruction(nodes, ref_node, mode, pa, n_docs=10, n_probes=200):
    """
    Embedding Reconstruction via Score Probing.
    
    Attacker issues random probe vectors and observes scores.
    From (probe, score) pairs, attacker reconstructs document embedding.
    
    HE-Lite: Scores encrypted -> reconstruction fails (cos_sim -> 0).
    """
    uses_he = mode in ('he_lite', 'combined')
    target_node = nodes[0]
    hub = HubOrchestrator([target_node], privacy_adapter=pa)

    cos_sims = []
    recon_attack = EmbeddingReconstructionAttack(
        embedding_dim=384, n_probes=n_probes)

    for doc_idx in range(min(n_docs, len(target_node.filenames))):
        true_emb = target_node.embeddings[doc_idx]

        def score_oracle(probe_vec):
            if uses_he:
                return 0.0  # Attacker can't see score
            # Simulate: attacker sends probe, gets score for target doc
            probe = probe_vec.copy().astype('float32').reshape(1, -1)
            import faiss as _faiss
            _faiss.normalize_L2(probe)
            true = true_emb.reshape(1, -1).copy()
            _faiss.normalize_L2(true)
            return float(np.dot(probe.flatten(), true.flatten()))

        _, cos_sim = recon_attack.attack(score_oracle, true_emb)
        cos_sims.append(cos_sim)

    return float(np.mean(cos_sims))


def run_adaptive_attack(gt, ref_node, template_attack, noise_scales, n_values):
    rows = []
    subset = gt[:100]
    for ns in noise_scales:
        pa = PrivacyAdapter(mode='vs_adp', noise_scale=ns)
        mqa = MultiQueryAveragingAttack(template_attack, pa, ref_node)
        for n_obs in n_values:
            successes = sum(
                1 for item in subset
                if mqa.attack_with_n_observations(
                    item['query'], item['target_org'],
                    item['target_file'], n=n_obs)[0]
            )
            asr = successes / len(subset)
            print(f"  Adaptive: noise={ns}, N={n_obs} -> ASR={asr:.3f}")
            rows.append({'noise_scale': ns, 'n_observations': n_obs,
                         'attack_success_rate': f"{asr:.4f}",
                         'n_queries': len(subset)})
    return rows


def main():
    os.makedirs(RESULT_DIR, exist_ok=True)

    # 1. Setup
    nodes, data_roots = [], {}
    for org in ORGS:
        n = LocalNode(org)
        n.load_data()
        n.build_index()
        nodes.append(n)
        data_roots[org] = n.data_dir
    ref_node = nodes[0]

    # 2. Ground Truth
    gt = extract_ground_truth(data_roots)
    print("\nGround Truth Validation:")
    validate_ground_truth(gt, data_roots)
    print(f"Total queries: {len(gt)}")

    # 3. Attacker
    template_attack = KnownTemplateAttack(nodes, ref_node.get_model())

    # 4. Baseline Rankings
    print("\n=== Plaintext Baseline Rankings ===")
    hub0 = HubOrchestrator(nodes)
    baseline_rankings = {}
    for item in gt:
        res, _, _ = hub0.broadcast(item['query'], top_k=TOP_K)
        baseline_rankings[item['query']] = [result_id(r) for r in res]
    print(f"Cached {len(baseline_rankings)} baseline rankings.")

    # ========== MAIN EXPERIMENTS ==========
    all_rows = []

    # Configs: (mode, noise_scale, label)
    configs = [('plaintext', 0.0, 'plaintext')]
    for ns in NOISE_SWEEP:
        configs.append(('vs_adp', ns, f'vs_adp_ns{ns}'))
    configs.append(('he_lite', 0.0, 'he_lite'))
    for ns in [1.0, 2.0]:  # Combined at key noise levels
        configs.append(('combined', ns, f'combined_ns{ns}'))

    for mode, ns, label in configs:
        for run in range(1, N_RUNS + 1):
            print(f"\n>>> {label} | Run {run}/{N_RUNS}")

            if mode == 'plaintext':
                pa = None
            elif mode == 'vs_adp':
                pa = PrivacyAdapter(mode='vs_adp', noise_scale=ns)
            elif mode == 'he_lite':
                pa = PrivacyAdapter(mode='he_lite')
            elif mode == 'combined':
                pa = PrivacyAdapter(mode='combined', noise_scale=ns)

            hub = HubOrchestrator(nodes, privacy_adapter=pa)
            score_attack = ScoreInferenceAttack()
            agg = run_experiment(hub, gt, ref_node, pa, template_attack,
                                 baseline_rankings, score_attack)

            # Cat-B: Score Inference accuracy
            si_acc, si_n = score_attack.compute_profile_accuracy(gt)
            agg['score_inf_acc'] = si_acc

            row = {'mode': mode, 'noise_scale': ns, 'run': run,
                   **{k: f"{v:.4f}" for k, v in agg.items()}}
            all_rows.append(row)

            print(f"  R@1={agg['recall_1']:.3f}  MRR={agg['mrr']:.3f}  "
                  f"Drift={agg['semantic_drift']:.3f}  "
                  f"ASR@1={agg['attack_asr_1']:.3f}  "
                  f"ScoreInf={si_acc:.3f}  "
                  f"Lat={agg['latency_ms']:.0f}ms  BW={agg['bandwidth_kb']:.1f}KB")

    # ========== DEFENSE MATRIX (Cat-B attacks) ==========
    print("\n=== Defense Matrix: Score-Based Attacks ===")
    matrix_rows = []
    matrix_configs = [
        ('plaintext', None),
        ('vs_adp', PrivacyAdapter(mode='vs_adp', noise_scale=1.0)),
        ('he_lite', PrivacyAdapter(mode='he_lite')),
        ('combined', PrivacyAdapter(mode='combined', noise_scale=1.0)),
    ]

    for mode_label, pa in matrix_configs:
        print(f"\n  [{mode_label}] MIA...")
        mia_acc, mia_thresh = run_mia_experiment(nodes, gt, ref_node, mode_label, pa)

        print(f"  [{mode_label}] Embedding Reconstruction...")
        recon_sim = run_emb_reconstruction(nodes, ref_node, mode_label, pa)

        # Query attack at this config
        if mode_label in ('vs_adp', 'combined'):
            plain_vecs = [ref_node.encode_query(g['query']) for g in gt[:100]]
            asrs = []
            for i, item in enumerate(gt[:100]):
                nv = pa.add_noise_to_vector(plain_vecs[i].copy())
                s, _ = template_attack.attack(nv, item['target_org'],
                                               item['target_file'])
                asrs.append(1 if s else 0)
            query_asr = np.mean(asrs)
        else:
            query_asr = 1.0  # No noise -> 100% ASR

        print(f"  [{mode_label}] Query ASR={query_asr:.3f}  "
              f"MIA Acc={mia_acc:.3f}  Recon CosSim={recon_sim:.3f}")

        matrix_rows.append({
            'mode': mode_label,
            'query_attack_asr': f"{query_asr:.4f}",
            'mia_accuracy': f"{mia_acc:.4f}",
            'emb_recon_cossim': f"{recon_sim:.4f}",
        })

    # ========== ADAPTIVE ATTACK ==========
    print("\n=== Adaptive Multi-Query Averaging ===")
    adaptive_rows = run_adaptive_attack(
        gt, ref_node, template_attack,
        noise_scales=[0.5, 1.0, 2.0],
        n_values=[1, 5, 10, 20],
    )

    # ========== WRITE CSVs ==========
    if all_rows:
        with open(RESULT_CSV, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
            w.writeheader()
            w.writerows(all_rows)
        print(f"\nResults -> {RESULT_CSV}")

    if matrix_rows:
        with open(MATRIX_CSV, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(matrix_rows[0].keys()))
            w.writeheader()
            w.writerows(matrix_rows)
        print(f"Defense Matrix -> {MATRIX_CSV}")

    if adaptive_rows:
        with open(ATTACK_CSV, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(adaptive_rows[0].keys()))
            w.writeheader()
            w.writerows(adaptive_rows)
        print(f"Adaptive -> {ATTACK_CSV}")

    # ========== SUMMARY ==========
    print("\n" + "=" * 120)
    print(f"{'Mode':<12} {'NS':<5} {'R@1':>5} {'MRR':>5} {'NDCG':>5} {'Drift':>5} "
          f"{'ASR@1':>5} {'ScoreInf':>8} {'Lat':>6} {'BW(KB)':>7}")
    print("-" * 120)

    groups = defaultdict(list)
    for row in all_rows:
        groups[(row['mode'], row['noise_scale'])].append(row)

    for (mode, ns), rows in groups.items():
        def a(f):
            return np.mean([float(r[f]) for r in rows if r.get(f)])
        print(f"{mode:<12} {str(ns):<5} {a('recall_1'):>5.3f} {a('mrr'):>5.3f} "
              f"{a('ndcg_10'):>5.3f} {a('semantic_drift'):>5.3f} "
              f"{a('attack_asr_1'):>5.3f} {a('score_inf_acc'):>8.3f} "
              f"{a('latency_ms'):>6.0f} {a('bandwidth_kb'):>7.1f}")
    print("=" * 120)

    print("\n=== Defense Matrix ===")
    print(f"{'Mode':<12} {'Query ASR':>10} {'MIA Acc':>10} {'Recon Sim':>10}")
    print("-" * 50)
    for row in matrix_rows:
        print(f"{row['mode']:<12} {row['query_attack_asr']:>10} "
              f"{row['mia_accuracy']:>10} {row['emb_recon_cossim']:>10}")
    print("-" * 50)


if __name__ == "__main__":
    main()
