# DECLARE generation with large language models

This project is my bachelor’s thesis. I create a pipeline to study how well LLMs can turn short natural language rules into **DECLARE** constraints. I start with a For each rule in natural language, the system asks an LLM to produce a DECLARE constraint. Then I compare that constraint against a **PHI** (ground-truth) constraint. I will translate both **PHI** and **PSI** (prediction) from DECLARE to LTLf and use the tool BLACK to check semantic equivalence (so two different, but equivalent formulas will count as correct). BLACK supports LTL/LTLf on finite traces and related logics. Unfortunately no DECLARE.

The repository aims to be easy to run and to reproduce. Code is in `src/`, sample test cases are in `testcases/`, and all results are written to `experiments/runs/` so it is always clear where outputs goes.

The goal is to test if LLMs can produce correct formal temporal constraints from natural language requirements, and to check both **syntactic correctness** (DECLARE) and **semantic equivalence** (LTLf with BLACK).

## Pipeline Overview

The workflow has two main branches:

### 1. Syntax Check (DECLARE)
- Input: DECLARE constraints (PHI).
- Step 1: **DECLARE to NL** (LLM A).
- Step 2: **NL to DECLARE** (LLM B).
- Output: DECLARE set PSI.
- Comparison: PHI vs. PHI (set difference).

### 2. Semantic Check (LTLf)
- Input: DECLARE constraints (PHI).
- Step 1: **DECLARE to LTLf** (with own mapping file based on Fionda).
- Output: LTLf PSI and PHI.
- Step 2: check semantic equivalence between PHI and PSI with **BLACK** (LTLf checker).



## How the project is organized

* `src/config.py` loads environment variables (API keys, seed), defines base paths, and keeps settings in one place. Put your keys in a local `.env` file (not committed to public git repo).

* `src/models/llm_runner.py` is a wrapper for the LLM APIs. It sends a fixed system prompt from `src/system_prompts/prompts.py` plus natural language rule, and parses the model’s answer. It currently supports OpenAI, Groq, and Gemini.

* `src/translate/declare_to_ltlf.py` translates DECLARE constraints to LTLf. It is based on the mapping in Fionda et al. 2013, with some additions and fixes.

* `src/eval/black_equivalence_checker.py` calls BLACK to check if two LTLf formulas are semantically equivalent. It uses subprocess to call the BLACK binary and parses the output.

* `src/pipeline/run_generation.py` reads test cases, calls the runner, and writes the model’s prediction. 

* `src/translate/prompts.py` has the system prompt for DECLARE rules etc. so it stays consistent across runs. 

* `src/utils/parse_utils.py` provides helper functions to parse the model’s output. 

## What you need to run it

You need Python 3 and at least one API key like an OpenAI API key or a Groq API key. 
Clone the repo, create and activate a venv, and create your `.env` file (store your API keys here).


### Setting up a Python environment on MacOS
```bash
python -m venv .venv
source .venv/bin/activate   
pip install -U pip
pip install openai python-dotenv pydantic tqdm pandas tabulate
cp .env.example .env  
```

`.env` contains:

```
OPENAI_API_KEY=abc123...
GROQ_API_KEY=def456...
GEMINI_API_KEY=ghi789...
```

No quotes are needed for the API keys.


## Data formats

* **Test cases (`testcases/*.txt`)**: one .txt file per test case with DECLARE formula. Example of the file `testcases/testcase1.txt`:

```
init(receive order)
end(close order)
exactly(receive order)
exactly(close order)
response(receive order, validate payment)
precedence(validate payment, pack items)
response(pack items, ship order)
neg-response(pack items, cancel order)
response(ship order, send invoice)
response(ship order, deliver order)
absence(2, cancel order)
response(cancel order, issue refund)
neg-response(cancel order, ship order)
not-coexistence(deliver order, issue refund)
```

* **Predictions (`experiments/runs`)**: A folder gets created with a timestamp and model names. Inside there is the summary.txt that lists the testcase file used, both LLMs that were used such as if the syntax and semantics were equivalent. Example:
```
  Summary
  Testcase: testcase1.txt
  LLM A (DECLARE to NL): google/gemini-1.5-flash  T=1.0
  LLM B (NL to DECLARE): openai/gpt-4o-mini  T=1.0

  SYNTAX DECLARE set comparison: DIFFERENT
  SEMANTICS LTLf equivalence: equivalent
```

Moreover a folder artifacts gets created with the full output of each step. There we can store the NL text that gets created by the LLM, the PSI DECLARE created such as the both LTLf formulas (PHI and PSI). I also created a `black.txt` that contains if PHI and PSI are equivalent according to BLACK such as both PHI and PSI in LTLf below each other for comparison. 
The file `declare_setdiff.txt` contains the set difference between PHI and PSI (syntax check).
 


## What is PHI?

PHI is the original DECLARE formula or from DECLARE translated into LTLf formula. PHI is then used as input by the LLM to generate NL text.

## What is PSI?
PSI is the predicted DECLARE formula from the LLM or the LTLf formula translated from the predicted DECLARE formula.

## Syntax check for DECLARE PHI and PSI
The syntax check compares the original DECLARE formula (PHI) with the predicted DECLARE formula (PSI) from the LLM. It checks if both sets of constraints are identical. If they are not, it lists the differences in `declare_setdiff.txt`.

## Semantic check for LTLf PHI and PSI using BLACK
The semantic check translates both the original DECLARE formula (PHI) and the predicted DECLARE formula (PSI) into LTLf using the mapping in `src/translate/declare_to_ltlf.py`. Then it uses BLACK to check if the two LTLf formulas are semantically equivalent. The result is stored in `black.txt`.




