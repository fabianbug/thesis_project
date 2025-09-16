from __future__ import annotations
import os, shutil, subprocess, tempfile
from pathlib import Path



def _find_exec(candidates: list[str]) -> str | None:
    for c in candidates:
        if not c:
            continue
        p = shutil.which(c) if "/" not in c else (str(Path(c)) if Path(c).exists() else None)
        if p:
            return p
    return None

def _xor(phi: str, psi: str) -> str:        # XOR for equivalence via UNSAT: (phi & !psi) | (!phi & psi)
    return f"(({phi}) & (!({psi}))) | ((!({phi})) & ({psi}))"

def _run(cmd: list[str]) -> str:            #Run a command and return combined stdout+stderr (uppercased).
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return (proc.stdout + proc.stderr).upper()

def _ascii(s: str) -> str:                  #Defensiv: swap Unicode to ASCII für CLIs.
    return (
        s.replace("¬", "!").replace("∧", "&").replace("∨", "|")
         .replace("→", "->").replace("⇒", "->").replace("↔", "<->").strip()
    )

# backends for equivalence checking BLACK and Aaltaf if blacksat fails


#Use BLACK CLI (black-sat) on XOR and return UNSAT
def _equiv_with_black(phi: str, psi: str, black_bin: str) -> bool: 
    phi = _ascii(phi); psi = _ascii(psi)
    xor = _xor(phi, psi)
    with tempfile.NamedTemporaryFile("w", suffix=".ltlf", delete=False) as tf:
        tf.write(xor)
        tmp = tf.name
    try:
        # Try common modes 'solve' or 'sat'
        for mode in ("solve", "sat"):
            out = _run([black_bin, "--logic", "ltlf", "--mode", mode, tmp])
            if "UNSAT" in out or "UNSATISFIABLE" in out:
                return True
            if "SAT" in out and "UNSAT" not in out:
                return False
        # If we get here, output was not recognized -> treat as non-equivalent
        raise RuntimeError(f"BLACK output not recognized.\n{out}")
    finally:
        Path(tmp).unlink(missing_ok=True)

def _equiv_with_aalta(phi: str, psi: str, aalta_bin: str) -> bool:
    """
    Fallback using Aaltaf (LTLf solver). 
    I check validity of (phi <-> psi):
      validity( (phi -> psi) & (psi -> phi) )
    """
    phi = _ascii(phi); psi = _ascii(psi)
    biimp = f"(({phi}) -> ({psi})) & (({psi}) -> ({phi}))"
    with tempfile.NamedTemporaryFile("w", suffix=".ltl", delete=False) as tf:
        tf.write(biimp)
        tmp = tf.name
    try:
        out = _run([aalta_bin, tmp])
        if "VALID" in out or "UNSAT" in out or "UNSATISFIABLE" in out:
            return True
        if "SAT" in out:
            return False

        raise RuntimeError(f"Aalta output not recognized.\n{out}")
    finally:
        Path(tmp).unlink(missing_ok=True)


# public APIs to call
def ltlf_equivalent(phi_ltlf: str, psi_ltlf: str) -> bool:      #Return True iff phi_ltlf ≡ psi_ltlf over finite traces.
    # 1) Try BLACK from common locations / PATH
    black_candidates = [
        os.environ.get("BLACK_BIN"),
        "./black/build/black-sat",
        "./black/bin/black-sat",
        "black-sat",   # PATH
        "black",       # some builds install as 'black'
    ]
    black = _find_exec(black_candidates)
    if black:
        try:
            return _equiv_with_black(phi_ltlf, psi_ltlf, black)
        except Exception as e:
            # If BLACK is found but errors out, we still attempt Aaltaf below.
            pass

    # 2) Fallback: Aaltaf (install/put on PATH), optional env override
    aalta_candidates = [
        os.environ.get("AALTA_BIN"),
        "aaltaf", "aalta",
        "/usr/local/bin/aaltaf", "/opt/homebrew/bin/aaltaf",
    ]
    aalta = _find_exec(aalta_candidates)
    if aalta:
        return _equiv_with_aalta(phi_ltlf, psi_ltlf, aalta)

    # 3) No solver available
    raise FileNotFoundError(
        "No LTLf solver found. Provide BLACK_BIN to black-sat, "
        "or install aaltaf and set AALTA_BIN / put it on PATH."
    )
