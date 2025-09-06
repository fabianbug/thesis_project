# LTLf generation with large language models

This project is my bachelor’s thesis. I study how well LLMs can turn short natural language rules into **LTLf** formulas. For each rule in natural language, the system asks an LLM to produce a formula. Then I compare that formula against a **gold** (ground‑truth) formula. Right now the comparison is a simple string check. 
Soon it will use the **BLACK** tool to check real semantic equivalence.

The repository is small on purpose and aims to be easy to run and to reproduce. Code lives in `src/`, sample test cases live in `data/testcases/`, and all results are written to `experiments/results/` so it is always clear where outputs goes.

## How the project is organized

* `src/config.py` loads environment variables (API keys, seed), defines base paths, and keeps settings in one place. Put your keys in a local `.env` file (not committed to public git repo).
* `src/models/openai_runner.py` is a wrapper around the OpenAI API. It sends a fixed system prompt `src/translate/prompts.py` plus natural language rule, asks for JSON output only, parses the model’s answer, and records lots of stuff like latency and token counts.
* `src/pipeline/run_generation.py` reads test cases, calls the runner, and writes one JSON line per case with the model’s prediction. It also includes small safety checks to make sure the gold formula is never sent to the model. (bc that would make the whole thing pointless)
* `src/pipeline/run_equivalence_check.py` reads predictions and gold formulas and produces a simple result per case (`parse_ok`, `equiv`). At the moment `equiv` is just string equality; later it will be a semantic check via BLACK.
* `src/translate/prompts.py` has the system prompt for LTLf rules etc. so it stays consistent across runs.
* `src/utils/io_utils.py` provides simple JSONL read/write helpers.

## What you need to run it

You need Python 3 and an API key for a LLM like an OpenAI API key. 
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

* **Test cases (`data/testcases/*.jsonl`)**: one JSON object per line with an `id`, a short English rule (`nl`), and a `gold` section with the correct formula. Example:

  `{"id":"T001","nl":"C must never occur.","gold":{"logic":"ltlf","formula":"G(!C)"}}`

* **Predictions (`experiments/results/*.jsonl`)**: one line per case with the model name, the predicted logic and formula, timing, token counts, and the raw API response for auditing.

* **Equivalence results**: one line per case with `parse_ok` and `equiv`. Right now `equiv` is true only if strings match exactly; later I will switch to BLACK.

## Reproducibility made practical

* **Temperature**: I use low values to make outputs stable. Default is 0.2; for official runs prefer 0.0–0.1 to minimize randomness.
* **Prompt hashing**: I store a SHA‑256 hash of the prompt. This cann potentially let me prove that two runs used the exact same prompt without storing the full prompt in every line. It also helps detect accidental prompt changes.
* **Gold fence**: before calling the model, the code checks that the gold formula does not appear in the system prompt or the NL text. This prevents the model from seeing the answer.
* **Logging**: I record latency and token usage so I can analyze cost and speed later. For potential evaluation.

## What is gold?

“Gold” is the ground truth. It is only used after generation to evaluate the model. The runner never sees it. The generation step gets only the natural language sentence plus the system prompt that defines the LTLf syntax the model must use.

## Evaluation

Now, the equivalence script simply checks that the predicted formula is not empty and compares strings. 
The next step is to integrate BLACK so I can decide whether two formulas are semantically equivalent (LTLf) even if they look different.

## Limits and next steps

For now I focus on LTLf. DECLARE support and bridges between LTLf and DECLARE are potentially on the roadmap. I will also add reports that summarize accuracy.

