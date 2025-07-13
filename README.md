# SAT_Solvers_MPI

This repository contains the source code for a comparative study of classical SAT-solving algorithms: Davis–Putnam (DP), DPLL, and pure Resolution. The goal is to benchmark their performance on both user-entered CNF formulas and large collections of DIMACS `.cnf` files.

The implementations draw on several foundational sources:

- **DP elimination** follows the textbook description from *Logic for Computer Science: Foundations of Automatic Theorem Proving* by Jean H. Gallier[^1].
- **DPLL optimizations** are inspired by the notebook [improving_sat_algorithms.ipynb][^2], corresponding to *Artificial Intelligence: A Modern Approach* by Stuart Russell and Peter Norvig[^3].
- **Resolution** is coded directly from the standard definition in Gallier’s text.

---

## Formula Representation

- **Literal**: an `int`, where positive means the variable and negative means its negation.  
  - Example: `-12` represents ¬x₁₂.
- **Clause**: a Python `list` of literals, understood as a disjunction.  
  - Example: `[1, -3, 4]` → (x₁ ∨ ¬x₃ ∨ x₄)
- **Formula**: a `list` of clauses, understood as a conjunction (CNF).  
  - Example: `[[1, -1], [2, -3]]` → (x₁ ∨ ¬x₁) ∧ (x₂ ∨ ¬x₃)

---

## Getting Started

These instructions assume a Unix-style environment (Linux/macOS) or Windows with PowerShell/Command Prompt. Adjust command syntax as needed.

### 1. Verify Python Version

Ensure you have **Python 3.7+** installed:

```bash
$ python3 --version
Python 3.10.8
