from pathlib import Path
import argparse
from src.models.openai_runner import OpenAIModel
from src.utils.io_utils import read_jsonl, write_jsonl
from src.config import EXP

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
        r = runner.generate(
            system_prompt="Convert NL to LTLf and return only JSON {\"logic\":\"ltlf\",\"formula\":\"...\"}.",
            nl_spec=ex["nl"],
        )
        rows.append({
            "id": ex["id"], "model": args.model,
            "pred": {"logic": r.logic, "formula": r.formula},
            "latency_ms": r.latency_ms,
            "tokens_in": r.tokens_in, "tokens_out": r.tokens_out,
            "raw": r.raw
        })
    write_jsonl(out, rows)
    print(f"Wrote {out}")

if __name__ == "__main__":
    main()
