import argparse, json
from pathlib import Path
from src.utils.io_utils import read_jsonl, write_jsonl
from src.eval.black_equivalence import is_parseable_ltlf

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", required=True)
    ap.add_argument("--phi", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    phi = {ex["id"]: ex for ex in read_jsonl(Path(args.phi))}
    out_rows = []
    for ex in read_jsonl(Path(args.pred)):
        phi_id = ex["id"]; pred = ex["pred"]["formula"]
        g = phi[phi_id]["phi"]["formula"]
        parse_ok = is_parseable_ltlf(pred)
        # Platzhalter-„Äquivalenz“: Stringgleichheit (nur für Smoke-Test!)
        equiv = (pred.replace(" ", "") == g.replace(" ", "")) if parse_ok else False
        out_rows.append({"id": phi_id, "model": ex["model"], "parse_ok": parse_ok, "equiv": equiv})
    write_jsonl(Path(args.out), out_rows)
    print(f"Wrote {args.out}")

if __name__ == "__main__":
    main()
