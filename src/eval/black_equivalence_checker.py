from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

__all__ = ["black_ltlf_equivalence"]

def _normalize(formula: str) -> str: 
    return " ".join(formula.split()).strip()

def _resolve_black_bin(user_bin: Optional[str] = None) -> str:
    if user_bin:
        return user_bin
    env_bin = os.environ.get("BLACK_BIN")
    if env_bin:
        return env_bin

    hb = "/opt/homebrew/opt/black-sat/bin/black"        # hb = Homebrew default path on Macs
    if Path(hb).exists() and os.access(hb, os.X_OK):
        return hb

    for name in ("black", "black-sat"):
        p = shutil.which(name)
        if p:
            return p
    
    return "black"

def _run_black_xor(phi: str, psi: str, *, black_bin: Optional[str], timeout: int, with_model: bool) -> str:
    # Executes BLACK with XOR formula and returns. No JSON, just text. (solve --finite)
    bin_path = _resolve_black_bin(black_bin)
    phi_n = _normalize(phi)
    psi_n = _normalize(psi)
    xor_formula = f"(({phi_n}) & !({psi_n})) | ((!({phi_n})) & ({psi_n}))"

    cmd = [bin_path, "solve", "--finite"]
    if with_model:
        cmd.append("-m")
    cmd += ["-f", xor_formula]

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    # if BLACK makes mistakes, we still want to see output
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()

    debug = Path("experiments/runs/_debug"); debug.mkdir(parents=True, exist_ok=True)
    (debug / "black_last_stdout.txt").write_text(out, encoding="utf-8")
    (debug / "black_last_stderr.txt").write_text(err, encoding="utf-8")

    if not out and proc.returncode not in (0, 1):
        raise RuntimeError(f"BLACK invocation failed (rc={proc.returncode}). Stderr:\n{err}")

    return out or err  

def black_ltlf_equivalence(
    phi: str,
    psi: str,
    *,
    black_bin: Optional[str] = None,
    timeout: int = 3600, # give it 1h just in case
    with_witness: bool = False, # if true, ask BLACK for a model on SAT (-m)
) -> bool:
    
    # checks semantic equivalence of phi and psi.
    out = _run_black_xor(phi, psi, black_bin=black_bin, timeout=timeout, with_model=with_witness)
    u = out.upper()

    # because XOR is UNSAT if equivalent, SAT if not equivalent 
    if "UNSAT" in u:
        return True
    if "SAT" in u:
        return False

    
    raise RuntimeError(f"Could not parse BLACK result. Output was:\n{out}")
