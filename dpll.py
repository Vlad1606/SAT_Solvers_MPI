"""
DPLL Solver with benchmark option

Usage:
  # Interactive DPLL on user-entered CNF
  $ python dpllsolver.py

  # Benchmark DPLL on a folder of DIMACS .cnf files
  $ python dpllsolver.py /path/to/cnf_directory --sample-per-block 10 --workers 4

Interactive mode: prompts for number of clauses, then each clause as integer literals ending with 0.

Benchmark mode: divides files into 10 equal blocks, samples N files per block (default N=10 for 100 total),
runs DPLL in parallel, and prints per-file times plus summary.
"""
import os
import sys
import glob
import random
import time
import argparse
import tracemalloc
from multiprocessing import Pool, cpu_count

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

def all_true(clauses, model):
    return all(any(lit in model for lit in clause) for clause in clauses)

def some_false(clauses, model):
    return any(all(-lit in model for lit in clause) for clause in clauses)

def unit_clause(clauses, model):
    for clause in clauses:
        survivors = [lit for lit in clause if -lit not in model]
        if len(survivors) == 1:
            lit = survivors[0]
            if lit not in model and -lit not in model:
                return lit
    return None

def pure_literal(clauses, model):
    counts = {}
    for clause in clauses:
        for lit in clause:
            if lit in model or -lit in model:
                continue
            counts.setdefault(abs(lit), set()).add(lit > 0)
    for var, signs in counts.items():
        if len(signs) == 1:
            return var if True in signs else -var
    return None

def simplify(clauses, var, value):
    new = []
    for clause in clauses:
        if (var if value else -var) in clause:
            continue
        reduced = [lit for lit in clause if lit != (-var if value else var)]
        new.append(reduced)
    return new

def dpll_rec(clauses, model):
    if all_true(clauses, model):
        return model
    if some_false(clauses, model):
        return None
    unit = unit_clause(clauses, model)
    if unit is not None:
        return dpll_rec(simplify(clauses, abs(unit), unit>0), model | {unit})
    pure = pure_literal(clauses, model)
    if pure is not None:
        return dpll_rec(simplify(clauses, abs(pure), pure>0), model | {pure})
    for clause in clauses:
        for lit in clause:
            if lit not in model and -lit not in model:
                var = abs(lit)
                res = dpll_rec(simplify(clauses, var, True), model | {var})
                if res is not None:
                    return res
                return dpll_rec(simplify(clauses, var, False), model | {-var})
    return None

def run_with_metrics(clauses):
    tracemalloc.start()
    start = time.time()
    result_model = dpll_rec(clauses, set())
    elapsed = time.time() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_mib = peak / (1024*1024)
    satisfiable = result_model is not None
    return satisfiable, elapsed, peak_mib

def interactive_mode():
    n = int(input("Enter number of clauses: "))
    print("Enter each clause:")
    lines = [input() for _ in range(n)]
    clauses = parse_dimacs_lines(lines)
    print("Solving...")
    sat, t, mem = run_with_metrics(clauses)
    print("Result:", "SATISFIABLE" if sat else "UNSATISFIABLE")
    print(f"Time elapsed: {t:.3f} seconds")
    print(f"Peak memory usage: {mem:.2f} MiB")

def worker_dpll(path):
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
    print(f"Sampling {len(samples)} of {total} files with {workers or cpu_count()} workers...\n")
    results = []
    pool = Pool(processes=workers or cpu_count())
    try:
        for res in pool.imap_unordered(worker_dpll, samples):
            results.append(res)
    except KeyboardInterrupt:
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

if __name__ == "__main__":
    main()
