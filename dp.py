"""
DP Solver with benchmark option

Usage:
  # Interactive DP on user‑entered CNF
  $ python dpsolver.py

  # Benchmark DP on a folder of DIMACS .cnf files
  $ python dpsolver.py /path/to/cnf_directory --sample-per-block 10 --workers 4

Interactive mode: prompts for number of clauses, then each clause as integer literals ending with 0.

Benchmark mode: divides files into 10 equal blocks, samples N files per block (default N=10 for 100 total),
runs DP in parallel, and prints per-file times plus summary.
"""
import os
import sys
import glob
import random
import time
import argparse
from multiprocessing import Pool, cpu_count
import tracemalloc

def parse_dimacs_file(path):
    clauses = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line[0] in ('c','%') or line.startswith('p'):
                continue
            lits = [int(x) for x in line.split() if x!='0']
            if lits:
                clauses.append(lits)
    return clauses

def parse_dimacs_lines(lines):
    clauses = []
    for line in lines:
        lits = [int(x) for x in line.strip().split() if x!='0']
        if lits:
            clauses.append(lits)
    return clauses

def find_unit_clause(clauses):
    for c in clauses:
        if len(c)==1:
            return c[0]
    return None

def unit_propagate(clauses, unit):
    new = []
    for c in clauses:
        if unit in c:
            continue
        if -unit in c:
            r = [lit for lit in c if lit!=-unit]
            if not r:
                return [[]]
            new.append(r)
        else:
            new.append(c)
    return new

def find_pure_literal(clauses):
    pol = {}
    for c in clauses:
        for lit in c:
            v = abs(lit)
            pol.setdefault(v, set()).add(lit>0)
    for v, signs in pol.items():
        if len(signs)==1:
            return v if True in signs else -v
    return None

def dp_eliminate(clauses):
    if any(len(c)==0 for c in clauses):
        return False
    if not clauses:
        return True
    p = find_pure_literal(clauses)
    if p is not None:
        return dp_eliminate([c for c in clauses if p not in c])
    u = find_unit_clause(clauses)
    if u is not None:
        return dp_eliminate(unit_propagate(clauses, u))
    lit0 = clauses[0][0]
    var = abs(lit0)
    pos = [c for c in clauses if var in c]
    neg = [c for c in clauses if -var in c]
    rest = [c for c in clauses if var not in c and -var not in c]
    resolvents = []
    for C in pos:
        for D in neg:
            R = [l for l in C if l!=var] + [l for l in D if l!=-var]
            R = list(dict.fromkeys(R))
            if not any(-l in R for l in R):
                resolvents.append(R)
    return dp_eliminate(rest + resolvents)

def run_with_metrics(clauses):

    tracemalloc.start()
    start = time.time()
    result = dp_eliminate(clauses)
    elapsed = time.time() - start
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_mib = peak / (1024 * 1024)
    return result, elapsed, peak_mib


def interactive_mode():
    n = int(input("Enter number of clauses: "))
    print("Enter each clause:")
    lines = [input() for _ in range(n)]
    clauses = parse_dimacs_lines(lines)
    print("Solving...")
    res, t, mem = run_with_metrics(clauses)
    print("Result:", "SATISFIABLE" if res else "UNSATISFIABLE")
    print(f"Time elapsed: {t:.3f} seconds")
    print(f"Peak memory usage: {mem:.2f} MiB")

def worker_dp(path):
    clauses = parse_dimacs_file(path)
    sat, elapsed, peak_mem = run_with_metrics(clauses)
    name = os.path.basename(path)
    print(f"{name}: {'SAT' if sat else 'UNSAT'} in {elapsed:.3f}s, {peak_mem:.2f}MiB", flush=True)
    return elapsed, sat, peak_mem, name

def benchmark_mode(folder, sample_per_block, workers):
    files = sorted(glob.glob(os.path.join(folder, "*.cnf")))
    if not files:
        print(f"No .cnf files in {folder}")
        return
    total = len(files)
    block_size = total // 10
    samples = []
    for i in range(10):
        blk = files[i*block_size:(i+1)*block_size] if i<9 else files[i*block_size:]
        picks = blk if len(blk)<=sample_per_block else random.sample(blk, sample_per_block)
        samples.extend(picks)
    print(f"Sampling {len(samples)} out of {total} files with {workers or cpu_count()} workers...\n")
    results = []
    pool = Pool(processes=workers or cpu_count())
    try:
        for res in pool.imap_unordered(worker_dp, samples):
            results.append(res)
    except KeyboardInterrupt:
        print("\nReceived interrupt — terminating workers…", file=sys.stderr)
        pool.terminate()
        pool.join()
        sys.exit(1)
    else:
        pool.close()
        pool.join()

    times = [e for e, _, _, _ in results]
    mems  = [m for _, _, m, _ in results]
    sats  = sum(1 for _, s, _, _ in results if s)
    uns   = len(results) - sats
    tot   = sum(times)
    avg_t = tot / len(times)
    fastest_idx = times.index(min(times))
    slowest_idx = times.index(max(times))
    leanest_idx  = mems.index(min(mems))
    heaviest_idx = mems.index(max(mems))

    print("\n=== Summary ===")
    print(f"Files tested           : {len(results)}")
    print(f"Satisfiable            : {sats}")
    print(f"Unsatisfiable          : {uns}")
    print(f"Total time             : {tot:.3f}s")
    print(f"Average time           : {avg_t:.3f}s")
    print(f"Fastest solve time     : {min(times):.3f}s ({results[fastest_idx][3]})")
    print(f"Slowest solve time     : {max(times):.3f}s ({results[slowest_idx][3]})")
    print(f"Lowest memory usage    : {min(mems):.2f} MiB ({results[leanest_idx][3]})")
    print(f"Highest memory usage   : {max(mems):.2f} MiB ({results[heaviest_idx][3]})")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('cnf_dir', nargs='?')
    parser.add_argument('--sample-per-block', type=int, default=10)
    parser.add_argument('--workers', type=int, default=0)
    args = parser.parse_args()
    random.seed()
    if args.cnf_dir and os.path.isdir(args.cnf_dir):
        benchmark_mode(args.cnf_dir, args.sample_per_block, args.workers)
    else:
        interactive_mode()

if __name__=="__main__":
    main()

