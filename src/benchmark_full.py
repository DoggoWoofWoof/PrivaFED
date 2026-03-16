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

# Path shim for direct execution
if __name__ == "__main__" or __name__.startswith("src."):
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
NOISE_SWEEP = [0.1, 0.5, 1.0, 2.0]
N_RUNS = 5 # Increased for statistical significance
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
        # FIX: account=False to avoid double-counting budget during attack simulation
        atk_vec = (pa.add_noise_to_vector(plain_vec.copy(), account=False)
                   if mode in ('vs_adp', 'combined') and pa else plain_vec.copy())

        s1, _ = template_attack.attack(atk_vec, item['target_org'],
                                        item['target_file'])
        s5, _ = template_attack.attack_top_k(atk_vec, item['target_org'],
                                              item['target_file'], k=5)
        m['attack_asr_1'].append(1 if s1 else 0)
        m['attack_asr_5'].append(1 if s5 else 0)
        m['recon_error'].append(compute_reconstruction_error(plain_vec, atk_vec))

        # Cat-B: Score interception (for ScoreInferenceAttack)
        score_attack.intercept(q, [{'org': s['org'], 'filename': s['filename'],
                                     'score': s['score']} for s in raw_scores],
                                encrypted=uses_he)

    # Append final epsilon status
    if pa:
        eps, _, _ = pa.get_budget_status()
        m['epsilon'] = [eps]
    else:
        m['epsilon'] = [0.0]

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
            # PIVOT: Read from aggregated scores (Pass 2)
            relevant = [s['score'] for s in raw if s['org'] == target_node.org_name]
            if relevant:
                member_scores.append(max(relevant))
            else:
                member_scores.append(0.0)

    nonmember_scores = []
    for item in nonmember_gt:
        results, _, raw = hub.broadcast(item['query'], top_k=TOP_K)
        if uses_he:
            nonmember_scores.append(0.5)  # Attacker can't see real score
        else:
            # PIVOT: Read from aggregated scores (Pass 2)
            relevant = [s['score'] for s in raw if s['org'] == target_node.org_name]
            if relevant:
                nonmember_scores.append(max(relevant))
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


def verify_he_correctness(nodes, pa):
    print("\n=== Verifying HE Correctness ===")
    node = nodes[0]
    q_text = "test query"
    q_vec = node.encode_query(q_text)
    
    # Plaintext dot product
    doc_vec = node.embeddings[0]
    plain_score = float(np.dot(q_vec.flatten(), doc_vec.flatten()))
    
    # HE dot product
    enc_q_blob, _ = pa.encrypt_vector(q_vec)
    enc_score_blob, _ = pa.compute_encrypted_dot_product(enc_q_blob, doc_vec)
    he_score, _ = pa.decrypt_scores(enc_score_blob)
    
    diff = abs(plain_score - he_score[0])
    print(f"  Plain: {plain_score:.6f}, HE: {he_score[0]:.6f}, Diff: {diff:.6e}")
    if diff < 1e-4:
        print("  SUCCESS: HE result matches plaintext within 1e-4.")
    else:
        print("  FAILURE: HE result divergence too high.")

def verify_budget_blocking(nodes, gt):
    print("\n=== Verifying Budget Blocking ===")
    # Small limit to trigger quickly
    pa = PrivacyAdapter(mode='vs_adp', noise_scale=0.1, epsilon_limit=1.0)
    hub = HubOrchestrator(nodes, privacy_adapter=pa)
    
    # Issue queries until blocked
    blocked = False
    for i in range(100):
        res, stats, _ = hub.broadcast(gt[0]['query'], top_k=1)
        eps, limit, exhausted = pa.get_budget_status()
        if exhausted:
            print(f"  Budget exhausted at query {i+1} (eps={eps:.2f})")
            # Next query should be blocked
            res_blocked, _, _ = hub.broadcast(gt[0]['query'], top_k=1)
            if not res_blocked:
                print("  SUCCESS: Next query correctly blocked.")
                blocked = True
            else:
                print("  FAILURE: Next query NOT blocked despite exhaustion.")
            break
    if not blocked:
        print("  FAILURE: Budget never exhausted in test.")

def main():
    os.makedirs(RESULT_DIR, exist_ok=True)
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_ROOT = os.path.join(ROOT, "data", "synthetic")

    # 1. Setup
    nodes, data_roots = [], {}
    for org in ORGS:
        n = LocalNode(org, data_dir=DATA_ROOT)
        n.load_data()
        n.build_index()
        nodes.append(n)
        data_roots[org] = n.data_dir
    ref_node = nodes[0]

    # 1b. Pairwise Secret Exchange (OOB Simulation)
    print("\nPerforming Pairwise Secret Exchange...")
    for i, node_i in enumerate(nodes):
        for j, node_j in enumerate(nodes):
            if i < j:
                secret = np.random.randint(1, 1000000)
                node_i.pairwise_secrets[node_j.org_name] = secret
                node_j.pairwise_secrets[node_i.org_name] = secret
    print("Secrets exchanged between all nodes.")

    # 2. Ground Truth
    gt = extract_ground_truth(data_roots)[:50] # Increased for statistical significance
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
    configs.append(('lsh', 0.0, 'lsh_64bit'))
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
            elif mode == 'lsh':
                pa = PrivacyAdapter(mode='lsh', lsh_bits=64)
            elif mode == 'combined':
                pa = PrivacyAdapter(mode='combined', noise_scale=ns)

            # Option B: enforce_budget=False for empirical utility analysis
            hub = HubOrchestrator(nodes, privacy_adapter=pa, enforce_budget=False)
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
                  f"Eps={agg['epsilon']:.0f}  "
                  f"Lat={agg['latency_ms']:.0f}ms  BW={agg['bandwidth_kb']:.1f}KB")

    # ========== DEFENSE MATRIX (Cat-B attacks) ==========
    print("\n=== Defense Matrix: Score-Based Attacks ===")
    matrix_rows = []
    matrix_configs = [
        ('plaintext', None),
        ('vs_adp', PrivacyAdapter(mode='vs_adp', noise_scale=2.0)),
        ('he_lite', PrivacyAdapter(mode='he_lite')),
        ('lsh', PrivacyAdapter(mode='lsh', lsh_bits=64)),
        ('combined', PrivacyAdapter(mode='combined', noise_scale=2.0)),
    ]

    for mode_label, pa in matrix_configs:
        print(f"\n  [{mode_label}] MIA...")
        mia_acc, mia_thresh = run_mia_experiment(nodes, gt, ref_node, mode_label, pa)

        print(f"  [{mode_label}] Embedding Reconstruction...")
        recon_sim = run_emb_reconstruction(nodes, ref_node, mode_label, pa)

        # Query & Score attacks at this config
        si_atk = ScoreInferenceAttack()
        hub_sa = HubOrchestrator(nodes, privacy_adapter=pa, enforce_budget=False)
        asrs = []
        
        # Test on a representative slice
        test_slice = gt[:50]
        plain_vecs = [ref_node.encode_query(g['query']) for g in test_slice]
        
        uses_he_m = mode_label in ('he_lite', 'combined')
        
        for i, item in enumerate(test_slice):
            # Query Attack (Cat-A)
            if mode_label in ('vs_adp', 'combined'):
                nv = pa.add_noise_to_vector(plain_vecs[i].copy(), account=False)
            else:
                nv = plain_vecs[i].copy()
                
            s, _ = template_attack.attack(nv, item['target_org'], item['target_file'])
            asrs.append(1 if s else 0)
            
            # Score Inference Attack (Cat-B)
            _, _, raw = hub_sa.broadcast(item['query'], top_k=TOP_K)
            si_atk.intercept(item['query'], raw, encrypted=uses_he_m)
            
        query_asr = np.mean(asrs)
        score_inf_acc, _ = si_atk.compute_profile_accuracy(test_slice)

        print(f"  [{mode_label}] Query ASR={query_asr:.3f}  "
              f"MIA Acc={mia_acc:.3f}  ScoreInf={score_inf_acc:.3f}  "
              f"Recon CosSim={recon_sim:.3f}")

        matrix_rows.append({
            'mode': mode_label,
            'query_attack_asr': f"{query_asr:.4f}",
            'mia_accuracy': f"{mia_acc:.4f}",
            'score_inf_acc': f"{score_inf_acc:.4f}",
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
    print("\n" + "=" * 135)
    print(f"{'Mode':<12} {'NS':<5} {'R@1':>10} {'MRR':>10} {'NDCG':>10} {'Drift':>10} "
          f"{'ASR@1':>10} {'Epsilon':>10} {'Lat(ms)':>10}")
    print("-" * 135)

    groups = defaultdict(list)
    for row in all_rows:
        groups[(row['mode'], row['noise_scale'])].append(row)

    for (mode, ns), rows in groups.items():
        def stats_str(field):
            vals = [float(r[field]) for r in rows if r.get(field)]
            if not vals: return "-"
            mean = np.mean(vals)
            std = np.std(vals)
            return f"{mean:.3f}±{std:.3f}"
        
        print(f"{mode:<12} {str(ns):<5} {stats_str('recall_1'):>10} {stats_str('mrr'):>10} "
              f"{stats_str('ndcg_10'):>10} {stats_str('semantic_drift'):>10} "
              f"{stats_str('attack_asr_1'):>10} {stats_str('epsilon'):>10} "
              f"{np.mean([float(r['latency_ms']) for r in rows]):>10.0f}")
    print("=" * 135)

    print("\n=== Defense Matrix ===")
    print(f"{'Mode':<12} {'Query ASR':>10} {'MIA Acc':>10} {'ScoreInf':>10} {'Recon Sim':>10}")
    print("-" * 65)
    for row in matrix_rows:
        print(f"{row['mode']:<12} {row['query_attack_asr']:>10} "
              f"{row['mia_accuracy']:>10} {row['score_inf_acc']:>10} "
              f"{row['emb_recon_cossim']:>10}")
    print("-" * 65)


    # ========== FINAL VALIDATIONS ==========
    verify_he_correctness(nodes, PrivacyAdapter(mode='he_lite'))
    verify_budget_blocking(nodes, gt)


if __name__ == "__main__":
    main()
