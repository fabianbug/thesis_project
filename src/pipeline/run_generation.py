from pathlib import Path
from hashlib import sha256
from datetime import datetime
import argparse
from src.models.openai_runner import OpenAIModel
from src.utils.io_utils import read_jsonl, write_jsonl
from src.config import EXP
from src.translate.prompts import PROMPT_LTLF_V1    # the system prompt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--temperature", type=float, default=0.2)
    args = ap.parse_args()

    runner = OpenAIModel(model=args.model, temperature=args.temperature)
    inp = Path(args.input)
    out = Path(args.out) if args.out else EXP / f"{inp.stem}_{args.model}.jsonl"

    rows = []
    for ex in read_jsonl(inp):
        
        #check that gold (ground truth) is not pasted to prompt
        nl = ex["nl"]
        gold = ex.get("gold", {}) or {}
        gold_formula = str(gold.get("formula", "") or "")
        if gold_formula:
            assert gold_formula not in PROMPT_LTLF_V1, "System prompt contains gold formula"
            assert gold_formula not in nl, "NL contains gold formula"
            
        #prompt sha hashed     
        to_send = PROMPT_LTLF_V1 + "\n" + nl
        prompt_sha = sha256(to_send.encode("utf-8")).hexdigest()

        r = runner.generate(
            system_prompt=PROMPT_LTLF_V1,
            nl_spec=nl,
        )
        rows.append({
            "id": ex["id"],
            "model": args.model,
            "pred": {"logic": r.logic, "formula": r.formula},
            "latency_ms": r.latency_ms,
            "tokens_in": r.tokens_in,
            "tokens_out": r.tokens_out,
            "raw": r.raw,
            "meta": {
                "system_ver": "ltlf_v1",
                "temperature": args.temperature,
                "prompt_sha256": prompt_sha,
                "ts_utc": datetime.utcnow().isoformat(timespec="seconds"),
                "model_id": r.raw.get("model") if isinstance(r.raw, dict) else None
            }
        })
    write_jsonl(out, rows)
    print(f"Wrote {out}")

if __name__ == "__main__":
    main()
