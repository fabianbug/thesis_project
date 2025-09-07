from pathlib import Path
from hashlib import sha256
from datetime import datetime
import argparse
from src.models.registry import create_runner
from src.utils.io_utils import read_jsonl, write_jsonl
from src.config import EXP
from src.translate.prompts import PROMPT_V1    # the system prompt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="openai", help="LLM provider id (default: openai)")
    ap.add_argument("--model", required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--temperature", type=float, default=0.1)
    args = ap.parse_args()

    runner = create_runner(provider=args.provider, model=args.model, temperature=args.temperature)

    inp = Path(args.input)
    out = Path(args.out) if args.out else EXP / f"{inp.stem}_{args.provider}_{args.model}.jsonl"

    rows = []

    for i, ex in enumerate(read_jsonl(inp), start=1):
        #ID for the example
        id = ex.get("id")
        
        #check that gold (ground truth) is not pasted to prompt
        nl = ex["nl"]
        gold = ex.get("gold", {}) 
        gold_formula = str(gold.get("ltlf", "declare") or "")
        # check that solution (gold formula) is not in prompt
        if gold_formula:
            assert gold_formula not in PROMPT_V1, "System prompt contains gold formula"
            assert gold_formula not in nl, "NL contains gold formula"
            
        #prompt sha hashed     
        to_send = PROMPT_V1 + "\n" + nl
        prompt_sha = sha256(to_send.encode("utf-8")).hexdigest()

        r = runner.generate(
            system_prompt=PROMPT_V1,
            nl_spec=nl,
        )
        rows.append({
            "id": id,
            "provider": args.provider,
            "model": args.model,
            "pred": {
                "ltlf": r.ltlf,
                "declare": r.declare,
            },
            "latency_ms": r.latency_ms,
            "tokens_in": r.tokens_in,
            "tokens_out": r.tokens_out,
            "raw": r.raw,
            "meta": {
                "system_ver": "ltlf+declare",
                "temperature": args.temperature,
                "prompt_sha256": prompt_sha,
                "ts_utc": datetime.now().isoformat(timespec="seconds"),
                "model_id": r.raw.get("model") if isinstance(r.raw, dict) else None
            }
        })
    write_jsonl(out, rows)
    print(f"Wrote {out}")

if __name__ == "__main__":
    main()
