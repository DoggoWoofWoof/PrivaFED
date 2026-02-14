import os
import re
import time
import json
import glob
import numpy as np
from src.local_retrieval import LocalNode

def extract_ground_truth(data_dir):
    """
    Parses generated files to create ground-truth query-document pairs.
    Returns a list of dicts: {'query': str, 'target_file': str}
    """
    ground_truth = []
    file_paths = glob.glob(os.path.join(data_dir, "*.txt"))
    
    # Regex to extract key entities based on our templates
    # Patterns:
    # "transaction {uuid}"
    # "account {iban}"
    # "Subject {name}"
    
    patterns = {
        'transaction_id': r"transaction ([0-9a-f-]{36})",
        'account_id': r"account ([A-Z0-9]+)", 
        # names are harder to regex reliably without knowing them, 
        # but we can try capturing capitalized words after "Subject" or "Customer"
    }

    print(f"Extracting ground truth from {len(file_paths)} files...")
    
    for path in file_paths:
        filename = os.path.basename(path)
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # create query based on transaction ID (high precision)
        match = re.search(patterns['transaction_id'], content)
        if match:
            transaction_id = match.group(1)
            ground_truth.append({
                'query': f"details for transaction {transaction_id}",
                'target_file': filename,
                'type': 'transaction_lookup'
            })
            
        # create query based on account ID
        match = re.search(patterns['account_id'], content)
        if match:
            account_id = match.group(1)
            # Use a more neutral query to rely on the ID match rather than template text
            ground_truth.append({
                'query': f"account {account_id} history",
                'target_file': filename,
                'type': 'account_lookup'
            })

    print(f"Generated {len(ground_truth)} test queries.")
    return ground_truth

def run_benchmark(org_name, k_values=[1, 5, 10]):
    node = LocalNode(org_name)
    node.load_data()
    node.build_index()
    
    ground_truth = extract_ground_truth(node.data_dir)
    
    if not ground_truth:
        print("No ground truth queries generated. Check data/regex.")
        return

    metrics = {k: 0 for k in k_values}
    latencies = []
    
    print(f"\nRunning benchmark on {len(ground_truth)} queries...")
    
    for item in ground_truth:
        query = item['query']
        target = item['target_file']
        
        results, latency = node.search(query, k=max(k_values))
        latencies.append(latency)
        
        retrieved_files = [res['filename'] for res in results]
        
        for k in k_values:
            if target in retrieved_files[:k]:
                metrics[k] += 1
                
    # Calculate averages
    total = len(ground_truth)
    print("\nBenchmark Results:")
    print(f"Total Queries: {total}")
    print(f"Average Latency: {np.mean(latencies):.2f} ms")
    
    for k in k_values:
        recall = metrics[k] / total
        print(f"Recall@{k}: {recall:.4f}")
        
    # FAILURE ANALYSIS
    print("\n--- Failure Analysis (Queries with Recall@10 = 0) ---")
    for item in ground_truth:
        query = item['query']
        target = item['target_file']
        
        # We need to re-run search or cache results, but for now let's just do a quick check
        # To avoid re-running everything, we can modify the loop above or just run a few examples here.
        # Better: let's print mismatches inside the main loop? 
        # Actually, let's just print them here if we stored them. 
        # Retrying the search for the failed ones is cleaner for this script.
        
        results, _ = node.search(query, k=10, rerank=True)
        retrieved_files = [res['filename'] for res in results]
        
        if target not in retrieved_files:
             print(f"FAILED: {query}")
             print(f"  Target: {target}")
             print(f"  Top 3 Found: {retrieved_files[:3]}")
             print(f"  Confusing Content in Top 1: {results[0]['content'][:100]}...\n")

    return metrics, np.mean(latencies)

if __name__ == "__main__":
    run_benchmark("org_A")
