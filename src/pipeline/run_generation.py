from __future__ import annotations
from pathlib import Path
from datetime import datetime
import argparse, os, sys

from src.system_prompts.prompts import NL_to_DECLARE, DECLARE_to_NL  # (NL_to_LTLf, LTLf_to_NL not needed here)
from src.models.registry import create_runner
from src.translate.declare_to_ltlf import declare_string_to_ltlf
from src.utils.parse_utils import parse_declare_set
from src.eval.black_equivalence_checker import black_ltlf_equivalence


def read_text(path: Path) -> str:
    return Path(path).read_text(encoding="utf-8").strip()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(content, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="NL <-> DECLARE <-> LTLf pipeline")

    # LLM A: DECLARE -> NL
    ap.add_argument("--provider-a", default="openai")
    ap.add_argument("--model-a", required=True, help="LLM A for DECLARE→NL")
    ap.add_argument("--temperature-a", type=float, default=1.0)

    # LLM B: NL -> DECLARE
    ap.add_argument("--provider-b", default="openai")
    ap.add_argument("--model-b", required=True, help="LLM B for NL→DECLARE")
    ap.add_argument("--temperature-b", type=float, default=1.0)

    # I/O
    ap.add_argument("--testcase", required=True, help="Plain-text file with DECLARE constraints (PHI).")
    ap.add_argument("--outdir", default="experiments/runs", help="Output directory.")

    # BLACK
    ap.add_argument("--black-bin", default=None, help="Path to black-sat binary (if not on PATH).")

    args = ap.parse_args()

    # Configure BLACK path to use ltlf_equivalent()
    if args.black_bin:
        os.environ["BLACK_BIN"] = args.black_bin

    # Create runners
    llm_a = create_runner(provider=args.provider_a, model=args.model_a, temperature=args.temperature_a)
    llm_b = create_runner(provider=args.provider_b, model=args.model_b, temperature=args.temperature_b)

    # Output folders
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_root = Path(args.outdir) / f"{stamp}_{args.model_a}_A__{args.model_b}_B"
    artifacts = out_root / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    # Read Input (DECLARE PHI) 
    phi_declare = read_text(Path(args.testcase))
    write_text(artifacts / "phi.declare.txt", phi_declare)

    # LLM A: DECLARE -> NL
    nl_from_declare = llm_a.generate(system=DECLARE_to_NL, user=phi_declare).strip()
    write_text(artifacts / "nl.txt", nl_from_declare)

    # LLM B: NL -> PSI DECLARE
    psi_declare = llm_b.generate(system=NL_to_DECLARE, user=nl_from_declare).strip()
    write_text(artifacts / "psi.declare.txt", psi_declare)



    # Syntactic comparison on DECLARE (is quite strict)
    set_phi = parse_declare_set(phi_declare)
    set_psi = parse_declare_set(psi_declare)
    missing = sorted(set_phi - set_psi)
    added   = sorted(set_psi - set_phi)
    syntactic_ok = (not missing and not added) # only if sets match exactly 

    syn_report = []
    syn_report.append("----- Syntactic comparison (DECLARE sets) -----")
    syn_report.append(f"original PHI={len(set_phi)}   after LLM translation PSI={len(set_psi)}")
    syn_report.append(f"OK? {syntactic_ok}")
    if missing:
        syn_report.append("Missing in PSI (present in PHI):")
        syn_report += [f"  - {c}" for c in missing]
    if added:
        syn_report.append("Added in PSI (not in PHI):")
        syn_report += [f"  + {c}" for c in added]
    write_text(artifacts / "declare_setdiff.txt", "\n".join(syn_report))



    # Encode both DECLARE specs to LTLf using mapper declare_to_ltlf.py
    phi_ltlf = declare_string_to_ltlf(phi_declare).strip()
    psi_ltlf = declare_string_to_ltlf(psi_declare).strip()
    write_text(artifacts / "phi.ltlf.txt", phi_ltlf)
    write_text(artifacts / "psi.ltlf.txt", psi_ltlf)

    # Semantic equivalence check with BLACK in LTLf
    # semantics_status = "error"
    try:  # this is in a try block because BLACK might fail
        is_equiv = black_ltlf_equivalence(phi_ltlf, psi_ltlf)
        semantics_status = "equivalent" if is_equiv else "not_equivalent"
        full_black = f"BLACK: {semantics_status}\nPHI: {phi_ltlf}\nPSI: {psi_ltlf}\n\n"
        write_text(artifacts / "black.txt", full_black)
    except Exception as e:
        semantics_status = f"skipped: {e.__class__.__name__}"

    # console summary
    summary = []
    summary.append("Summary")
    summary.append(f"Testcase: {Path(args.testcase).name}")
    summary.append(f"LLM A (DECLARE to NL): {args.provider_a}/{args.model_a}  T={args.temperature_a}")
    summary.append(f"LLM B (NL to DECLARE): {args.provider_b}/{args.model_b}  T={args.temperature_b}")
    summary.append("")
    summary.append(f"SYNTAX DECLARE set comparison: {'EQUIVALENT' if syntactic_ok else 'DIFFERENT'}")
    summary.append(f"SEMANTICS LTLf equivalence: {semantics_status}")
    write_text(out_root / "summary.txt", "\n".join(summary))

    # Console output
    print("\n".join(summary))
    print(f"\nArtifacts written to: {out_root}\n")


if __name__ == "__main__":
    sys.exit(main())
