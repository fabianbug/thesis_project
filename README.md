# DECLARE generation with large language models

This project is my bachelor’s thesis. I create a pipeline to study how well LLMs can turn short natural language rules into **DECLARE** constraints. I start with a For each rule in natural language, the system asks an LLM to produce a DECLARE constraint. Then I compare that constraint against a **PHI** (ground-truth) constraint. I will translate both **PHI** and **PSI** (prediction) from DECLARE to LTLf and use the tool BLACK to check semantic equivalence (so two different, but equivalent formulas will count as correct). BLACK supports LTL/LTLf on finite traces and related logics. Unfortunately no DECLARE.

The repository aims to be easy to run and to reproduce. Code is in `src/`, sample test cases are in `testcases/`, and all results are written to `experiments/runs/` so it is always clear where outputs goes.

