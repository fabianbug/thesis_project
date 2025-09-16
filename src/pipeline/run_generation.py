from __future__ import annotations
from pathlib import Path
from datetime import datetime
import argparse, os, sys

from src.system_prompts.prompts import NL_to_DECLARE, DECLARE_to_NL, NL_to_LTLf, LTLf_to_NL
from src.models.registry import create_runner
from src.translate.declare_to_ltlf import declare_string_to_ltlf
from src.utils.parse_utils import parse_declare_set
from src.eval.black_equivalence_checker import ltlf_equivalent


# Uses two LLMs:
#   - LLM_A: DECLARE->NL  and  LTLf->NL
#   - LLM_B: NL->DECLARE  and  NL->LTLf


def read_text(path: Path) -> str:
    return Path(path).read_text(encoding="utf-8").strip()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(content, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="One-pass NL↔DECLARE↔LTLf pipeline (two LLMs, string-only).")
    
    # LLM A (DECLARE to NL and LTLf to NL)
    ap.add_argument("--provider-a", default="openai")
    ap.add_argument("--model-a", required=True, help="LLM A for DECLARE to NL and LTLf to NL")
    ap.add_argument("--temperature-a", type=float, default=1.0)

    # LLM B (NL to DECLARE and NL to LTLf)
    ap.add_argument("--provider-b", default="openai")
    ap.add_argument("--model-b", required=True, help="LLM B for NL to DECLARE and NL to LTLf")
    ap.add_argument("--temperature-b", type=float, default=1.0)

    # IO
    ap.add_argument("--testcase", required=True, help="Plain-text file with DECLARE constraints (ϕ).")
    ap.add_argument("--outdir", default="experiments/runs", help="Output directory for artifacts.")
    ap.add_argument("--black-bin", default=None, help="Optional path to black-sat (if not on PATH).")

    args = ap.parse_args()

    # BLACK path via env var für den Checker
    if args.black_bin:
        os.environ["BLACK_BIN"] = args.black_bin

    # Runner erzeugen
    llm_a = create_runner(provider=args.provider_a, model=args.model_a, temperature=args.temperature_a)
    llm_b = create_runner(provider=args.provider_b, model=args.model_b, temperature=args.temperature_b)

    # Run-Verzeichnis
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_root = Path(args.outdir) / f"{stamp}_{args.model_a}_A__{args.model_b}_B"
    artifacts = out_root / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    # 1) Input PHI DECLARE einlesen
    phi_declare = read_text(Path(args.testcase))
    write_text(artifacts / "phi.declare.txt", phi_declare)

    # BRANCH A: DECLARE ↔ NL
    # A1: PHI DECLARE -> NL  (LLM A)
    nl_from_declare = llm_a.generate(system=DECLARE_to_NL, user=phi_declare).strip()
    write_text(artifacts / "phi.nl.txt", nl_from_declare)

    # A2: NL -> PSI DECLARE   (LLM B)
    psi_declare = llm_b.generate(system=NL_to_DECLARE, user=nl_from_declare).strip()
    write_text(artifacts / "psi.declare.txt", psi_declare)

    # A3: Syntaktischer Vergleich (Set-Diff)
    set_phi = parse_declare_set(phi_declare)
    set_psi = parse_declare_set(psi_declare)
    missing = sorted(set_phi - set_psi)
    added   = sorted(set_psi - set_phi)
    syntactic_ok = (not missing and not added)

    report_syn = []
    report_syn.append("=== Syntactic comparison (DECLARE sets) ===")
    report_syn.append(f"original PHI={len(set_phi)}   roundtrip PSI={len(set_psi)}")
    report_syn.append(f"OK? {syntactic_ok}")
    if missing:
        report_syn.append("Missing in PSI (present in PHI):")
        report_syn += [f"  - {c}" for c in missing]
    if added:
        report_syn.append("Added in PSI (not in PHI):")
        report_syn += [f"  + {c}" for c in added]
    write_text(artifacts / "declare_setdiff.txt", "\n".join(report_syn))

    # BRANCH B: DECLARE → LTLf ↔ NL ↔ LTLf (Semantic check) 
    # B1: PHI DECLARE -> PHI LTLf (encoder)
    phi_ltlf = declare_string_to_ltlf(phi_declare).strip()
    write_text(artifacts / "phi.ltlf.txt", phi_ltlf)

    # B2: PHI LTLf -> NL  (LLM A)
    nl_from_ltlf = llm_a.generate(system=LTLf_to_NL, user=phi_ltlf).strip()
    write_text(artifacts / "phiL.nl.txt", nl_from_ltlf)

    # B3: NL -> PSI LTLf  (LLM B)
    psi_ltlf = llm_b.generate(system=NL_to_LTLf, user=nl_from_ltlf).strip()
    write_text(artifacts / "psi.ltlf.txt", psi_ltlf)

    # B4: semantic equivalence (BLACK/Aaltaf). skipped if no solver is there
    semantics_status = "skipped"
    try:
        is_equiv = ltlf_equivalent(phi_ltlf, psi_ltlf)
        semantics_status = "equivalent" if is_equiv else "not_equivalent"
    except Exception as e:
        semantics_status = f"skipped: {e.__class__.__name__}"

    





    summary_lines = []
    summary_lines.append("=== Round-trip Summary ===")
    summary_lines.append(f"Testcase: {Path(args.testcase).name}")
    summary_lines.append(f"LLM A (DECLARE->NL, LTLf->NL): {args.provider_a}/{args.model_a}  T={args.temperature_a}")
    summary_lines.append(f"LLM B (NL->DECLARE, NL->LTLf): {args.provider_b}/{args.model_b}  T={args.temperature_b}")
    summary_lines.append("")
    summary_lines.append(f"[Syntax] DECLARE set comparison: {'OK' if syntactic_ok else 'DIFF'}")
    summary_lines.append(f"[Semantics] LTLf equivalence: {semantics_status}")
    write_text(out_root / "summary.txt", "\n".join(summary_lines))

    # Console-Output
    print("\n".join(summary_lines))
    print(f"\nArtifacts written to: {out_root}\n")


if __name__ == "__main__":
    # Allow running via: python -m src.pipeline.run_generation --args...
    sys.exit(main())
