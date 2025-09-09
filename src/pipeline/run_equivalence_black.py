# src/pipeline/run_equivalence_black.py
# Check DECLARE→LTLf equivalence (PHI ↔ PSI) by delegating to BLACK CLI.
# - Reads testcases (JSONL) with PHI as DECLARE
# - Reads predictions (JSONL) with PSI as DECLARE
# - Translates both to LTLf using src.translate.declare_to_ltlf
# - Calls BLACK CLI for validity/sat checks (no custom solver logic)
#
# Usage example:
#   python -m src.pipeline.run_equivalence_black \
#       --testcases data/testcases/testcases.jsonl \
#       --predictions experiments/results/testcases_openai_gpt-5_t0.2_20250909-093736.jsonl \
#       --out experiments/results/equiv_gpt-5_20250909.jsonl \
#       --include_ltlf --include_witnesses
#
# IMPORTANT: BLACK build flags/tokens can differ. Use the CLI args below to adapt:
#   --black-bin black --black-logic ltlf --black-valid-mode valid --black-sat-mode sat
#   --valid-token VALID --unsat-token UNSAT

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Iterable, Tuple, Optional
import argparse
import json
import sys
from datetime import datetime
import subprocess
import shlex

from src.translate.declare_to_ltlf import (
    translate_phi_json,
    translate_psi_json,
    Iff, And, Not  # reuse helpers to build formulas
)

# ---------- JSONL helpers ----------

def read_jsonl(p: Path) -> Iterable[Dict[str, Any]]:
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)

def write_jsonl(p: Path, rows: Iterable[Dict[str, Any]]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

# ---------- PSI extraction (robust gegen Schemas) ----------

def _extract_psi_obj(pred_row: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """
    Return (psi_obj, source_hint). Tries common fields:
      - psi / prediction / output / result
      Each may be dict with 'declare', or a JSON string with that dict.
      Fallback: top-level 'declare'.
    """
    for k in ("psi", "prediction", "output", "result"):
        if k in pred_row and pred_row[k] is not None:
            v = pred_row[k]
            if isinstance(v, dict) and "declare" in v:
                return v, k
            if isinstance(v, str):
                try:
                    vv = json.loads(v)
                    if isinstance(vv, dict) and "declare" in vv:
                        return vv, f"{k}(json)"
                except Exception:
                    pass
    if "declare" in pred_row and isinstance(pred_row["declare"], list):
        return {"declare": pred_row["declare"]}, "declare(top)"
    raise KeyError("No PSI DECLARE structure found in prediction row.")

# ---------- BLACK CLI wrappers (pure delegation) ----------

def black_valid(formula: str, *, black_bin: str, logic: str, mode_valid: str,
                valid_token: str) -> bool:
    """
    Ask BLACK if 'formula' is valid (tautology) under the given logic/mode.
    """
    cmd = f'{shlex.quote(black_bin)} --logic {shlex.quote(logic)} --mode {shlex.quote(mode_valid)} {shlex.quote(formula)}'
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"BLACK valid failed: {res.stderr.strip() or res.stdout.strip()}")
    return valid_token.upper() in res.stdout.upper()

def black_sat(formula: str, *, black_bin: str, logic: str, mode_sat: str,
              unsat_token: str) -> Optional[str]:
    """
    Ask BLACK if 'formula' is satisfiable. If UNSAT, return None.
    Else return raw witness text (stdout) so we don't guess its format.
    """
    cmd = f'{shlex.quote(black_bin)} --logic {shlex.quote(logic)} --mode {shlex.quote(mode_sat)} {shlex.quote(formula)}'
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"BLACK sat failed: {res.stderr.strip() or res.stdout.strip()}")
    out_up = res.stdout.upper()
    if unsat_token.upper() in out_up:
        return None
    return res.stdout.strip() or res.stderr.strip()

# ---------- Main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--testcases", required=True, help="JSONL with PHI as DECLARE per id")
    ap.add_argument("--predictions", required=True, help="JSONL with PSI as DECLARE per id")
    ap.add_argument("--out", default=None, help="Output JSONL; default derives from predictions file name")
    ap.add_argument("--max_cases", type=int, default=0, help="Limit number of evaluated cases (0 = no limit)")
    ap.add_argument("--include_ltlf", action="store_true", help="Include PHI/PSI LTLf strings in the output")
    ap.add_argument("--include_witnesses", action="store_true", help="Include BLACK witnesses if available")

    # BLACK config (parametrisierbar!)
    ap.add_argument("--black-bin", default="black", help="BLACK executable name/path")
    ap.add_argument("--black-logic", default="ltlf", help="BLACK --logic value (default: ltlf)")
    ap.add_argument("--black-valid-mode", default="valid", help="BLACK mode for validity checking")
    ap.add_argument("--black-sat-mode", default="sat", help="BLACK mode for satisfiability checking")
    ap.add_argument("--valid-token", default="VALID", help="Token printed by BLACK on validity success")
    ap.add_argument("--unsat-token", default="UNSAT", help="Token printed by BLACK when a formula is unsatisfiable")

    args = ap.parse_args()

    tc_path = Path(args.testcases)
    pred_path = Path(args.predictions)
    if args.out:
        out_path = Path(args.out)
    else:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        out_path = pred_path.parent / f"equivalence_{pred_path.stem}_{ts}.jsonl"

    # Load testcases -> map id -> phi.declare
    phi_by_id: Dict[str, Dict[str, Any]] = {}
    for row in read_jsonl(tc_path):
        rid = str(row.get("id") or row.get("case_id") or row.get("uid") or "")
        if not rid:
            print(f"[WARN] testcase row without id: {row}", file=sys.stderr)
            continue
        phi = row.get("phi")
        if not phi or not isinstance(phi, dict) or "declare" not in phi:
            print(f"[WARN] testcase {rid}: missing phi.declare", file=sys.stderr)
            continue
        phi_by_id[rid] = phi

    if not phi_by_id:
        print("[ERROR] No valid testcases with phi.declare found.", file=sys.stderr)
        sys.exit(2)

    out_rows = []
    n_total = n_eval = n_equiv = n_parse_err = n_black_err = 0

    for i, prow in enumerate(read_jsonl(pred_path), start=1):
        n_total += 1
        if args.max_cases and n_eval >= args.max_cases:
            break

        rid = str(prow.get("id") or prow.get("case_id") or prow.get("uid") or "")
        if not rid:
            rid = f"row_{i}"

        base = {"id": rid, "source_file": str(pred_path)}

        if rid not in phi_by_id:
            out_rows.append({**base, "status": "skip", "reason": "phi_not_found"})
            continue

        try:
            # DECLARE -> LTLf
            phi_res = translate_phi_json(phi_by_id[rid])
            psi_obj, psi_src = _extract_psi_obj(prow)
            psi_res = translate_psi_json(psi_obj)

            # φ ↔ ψ
            biimp = Iff(phi_res.ltlf, psi_res.ltlf)
            is_equiv = black_valid(
                biimp,
                black_bin=args.black_bin,
                logic=args.black_logic,
                mode_valid=args.black_valid_mode,
                valid_token=args.valid_token,
            )

            row_out: Dict[str, Any] = {
                **base,
                "status": "ok",
                "equiv": bool(is_equiv),
                "psi_source": psi_src,
            }

            if args.include_ltlf:
                row_out["phi_ltlf"] = phi_res.ltlf
                row_out["psi_ltlf"] = psi_res.ltlf

            if not is_equiv and args.include_witnesses:
                # Gegenbeispiele:
                w1 = black_sat(
                    And(phi_res.ltlf, Not(psi_res.ltlf)),
                    black_bin=args.black_bin,
                    logic=args.black_logic,
                    mode_sat=args.black_sat_mode,
                    unsat_token=args.unsat_token,
                )
                w2 = black_sat(
                    And(psi_res.ltlf, Not(phi_res.ltlf)),
                    black_bin=args.black_bin,
                    logic=args.black_logic,
                    mode_sat=args.black_sat_mode,
                    unsat_token=args.unsat_token,
                )
                if w1:
                    row_out["phi_and_not_psi"] = w1
                if w2:
                    row_out["psi_and_not_phi"] = w2

            out_rows.append(row_out)
            n_eval += 1
            if is_equiv:
                n_equiv += 1

        except KeyError as e:
            out_rows.append({**base, "status": "error", "error": f"psi_missing: {e}"})
            n_parse_err += 1
        except Exception as e:
            out_rows.append({**base, "status": "error", "error": f"black_or_translate: {e}"})
            n_black_err += 1

    write_jsonl(out_path, out_rows)
    print(
        f"[SUMMARY] total={n_total} evaluated={n_eval} equiv={n_equiv} "
        f"errors_parse={n_parse_err} errors_black={n_black_err} out={out_path}",
        file=sys.stderr,
    )

if __name__ == "__main__":
    main()
