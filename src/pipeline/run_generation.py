from pathlib import Path
from hashlib import sha256
from datetime import datetime
import argparse
from src.models.registry import create_runner
from src.utils.io_utils import read_jsonl, write_jsonl
from src.config import EXP
from src.translate.prompts import SYSTEM_PROMPT    # the system prompt
from src.pipeline.response_json_handling import LLMResponse, _extract_json

#from src.translate.declare_to_ltlf import # todo declare_to_ltlf 


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="openai")
    ap.add_argument("--model", default="gpt-5")
    ap.add_argument("--input", default="data/testcases/testcases.jsonl")
    ap.add_argument("--out", default=None)
    ap.add_argument("--temperature", type=float, default=1.0) # for tuning creativity 
    args = ap.parse_args()

    runner = create_runner(provider=args.provider, model=args.model, temperature=args.temperature)

    input_path = Path(args.input) or Path("data/testcases/testcases.jsonl") # path to testcase file
    output_path = Path(args.out) if args.out else Path("experiments/results") # output directory
    output_path.mkdir(parents=True, exist_ok=True) 
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base  = f"{input_path.stem}_{args.provider}_{args.model}_t{args.temperature:.1f}_{stamp}"
    result_path = output_path / f"{base}.jsonl"
    print(f"Input: {input_path}, Output: {result_path}")
    
    rows = []

    for i, ex in enumerate(read_jsonl(input_path), start=1):
        #ID for the example
        id = ex.get("id")
        
        #check that phi (ground truth) is not pasted to prompt
        nl = ex["nl"]
        phi = ex.get("phi", {}) 
        phi_formula = str(phi.get("declare") or "")
        # check that solution (phi) is not in prompt
        if phi_formula:
            assert phi_formula not in SYSTEM_PROMPT, "System prompt contains gold formula"
            assert phi_formula not in nl, "NL contains gold formula"
            
        #prompt sha hashed     
        to_send = SYSTEM_PROMPT + "\n" + nl
        prompt_sha = sha256(to_send.encode("utf-8")).hexdigest()

        r = runner.generate(
            system_prompt=SYSTEM_PROMPT,
            nl_spec=nl,
        )
        rows.append({
            "id": id,
            "provider": args.provider,
            "model": args.model,
            "psi_declare": r.declare,
            "latency_ms": r.latency_ms,
            "tokens_in": r.tokens_in,
            "tokens_out": r.tokens_out,
            "raw": r.raw,
            "meta": {
                "system_ver": "declare",
                "temperature": args.temperature,
                "prompt_sha256": prompt_sha,
                "ts_utc": datetime.now().isoformat(timespec="seconds"),
                "model_id": r.raw.get("model") if isinstance(r.raw, dict) else None
            }
        })
    write_jsonl(result_path, rows)
    print(f"Wrote {result_path}")

if __name__ == "__main__":
    main()
