from __future__ import annotations
from pathlib import Path
from datetime import datetime
import argparse, os, sys

from src.system_prompts.prompts import NL_to_DECLARE, DECLARE_to_NL  # (NL_to_LTLf, LTLf_to_NL not needed here)
from src.models.registry import create_runner
from src.translate.declare_to_ltlf import declare_string_to_ltlf
from src.utils.parse_utils import parse_declare_set
from src.eval.black_equivalence_checker import ltlf_equivalent


def read_text(path: Path) -> str:
    return Path(path).read_text(encoding="utf-8").strip()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(content, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Minimal NL↔DECLARE↔LTLf pipeline (two LLMs, no JSON).")

    # LLM A: DECLARE -> NL
    ap.add_argument("--provider-a", default="openai")
    ap.add_argument("--model-a", required=True, help="LLM A for DECLARE→NL")
    ap.add_argument("--temperature-a", type=float, default=0.2)

    # LLM B: NL -> DECLARE
    ap.add_argument("--provider-b", default="openai")
    ap.add_argument("--model-b", required=True, help="LLM B for NL→DECLARE")
    ap.add_argument("--temperature-b", type=float, default=0.2)

    # IO
    ap.add_argument("--testcase", required=True, help="Plain-text file with DECLARE constraints (PHI).")
    ap.add_argument("--outdir", default="experiments/runs", help="Output directory for artifacts.")

    # BLACK
    ap.add_argument("--black-bin", default=None, help="Optional path to black-sat binary (if not on PATH).")

    args = ap.parse_args()

    # Configure BLACK path for ltlf_equivalent()
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

    # === 1) Read PHI DECLARE (input) ===
    phi_declare = read_text(Path(args.testcase))
    write_text(artifacts / "phi.declare.txt", phi_declare)

    # === 2) DECLARE -> NL (LLM A) ===
    nl_from_declare = llm_a.generate(system=DECLARE_to_NL, user=phi_declare).strip()
    write_text(artifacts / "phi.nl.txt", nl_from_declare)

    # === 3) NL -> PSI DECLARE (LLM B) ===
    psi_declare = llm_b.generate(system=NL_to_DECLARE, user=nl_from_declare).strip()
    write_text(artifacts / "psi.declare.txt", psi_declare)

    # === 4) Syntactic set comparison on DECLARE ===
    set_phi = parse_declare_set(phi_declare)
    set_psi = parse_declare_set(psi_declare)
    missing = sorted(set_phi - set_psi)
    added   = sorted(set_psi - set_phi)
    syntactic_ok = (not missing and not added)

    syn_report = []
    syn_report.append("=== Syntactic comparison (DECLARE sets) ===")
    syn_report.append(f"original PHI={len(set_phi)}   roundtrip PSI={len(set_psi)}")
    syn_report.append(f"OK? {syntactic_ok}")
    if missing:
        syn_report.append("Missing in PSI (present in PHI):")
        syn_report += [f"  - {c}" for c in missing]
    if added:
        syn_report.append("Added in PSI (not in PHI):")
        syn_report += [f"  + {c}" for c in added]
    write_text(artifacts / "declare_setdiff.txt", "\n".join(syn_report))

    # === 5) Encode both DECLARE specs to LTLf via tool ===
    phi_ltlf = declare_string_to_ltlf(phi_declare).strip()
    psi_ltlf = declare_string_to_ltlf(psi_declare).strip()
    write_text(artifacts / "phi.ltlf.txt", phi_ltlf)
    write_text(artifacts / "psi.ltlf.txt", psi_ltlf)

    # === 6) Semantic equivalence check in LTLf (BLACK) ===
    semantics_status = "skipped"
    try:
        is_equiv = ltlf_equivalent(phi_ltlf, psi_ltlf)
        semantics_status = "equivalent" if is_equiv else "not_equivalent"
    except Exception as e:
        semantics_status = f"skipped: {e.__class__.__name__}"

    # console summary
    summary = []
    summary.append("Summary")
    summary.append(f"Testcase: {Path(args.testcase).name}")
    summary.append(f"LLM A (DECLARE→NL): {args.provider_a}/{args.model_a}  T={args.temperature_a}")
    summary.append(f"LLM B (NL→DECLARE): {args.provider_b}/{args.model_b}  T={args.temperature_b}")
    summary.append("")
    summary.append(f"[Syntax] DECLARE set comparison: {'EQUIVALENT' if syntactic_ok else 'DIFFERENT'}")
    summary.append(f"[Semantics] LTLf equivalence: {semantics_status}")
    write_text(out_root / "summary.txt", "\n".join(summary))

    # Console
    print("\n".join(summary))
    print(f"\nArtifacts written to: {out_root}\n")


if __name__ == "__main__":
    sys.exit(main())
