import re
from typing import List, Set
from src.translate.declare_to_ltlf import ALIASES  

# 

_DEF_SPLIT = re.compile(r"[;\n]+")
_TPL_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_\-\s]*)\s*\(\s*([^)]+)\s*\)\s*$")

_COMMUTATIVE = {
    "choice", "exclusive-choice",
    "coexistence", "not-coexistence",
}

def split_declare(spec: str) -> List[str]:
    if not spec:
        return []
    parts = _DEF_SPLIT.split(spec.strip())
    return [p.strip() for p in parts if p.strip()]

def _canon_tpl(tpl: str) -> str:
    t = tpl.strip().lower().replace(" ", "-")
    return ALIASES.get(t, t)

def _canon_arg(a: str) -> str:
    a = re.sub(r"\s+", " ", a.strip())
    return a

def normalize_constraint(c: str) -> str:
    m = _TPL_RE.match(c)
    if not m:
        return c.strip()

    tpl = _canon_tpl(m.group(1))
    args_raw = [s for s in m.group(2).split(",")]
    args = [_canon_arg(a) for a in args_raw]

    if tpl in {"existence", "absence", "exactly"}:
        if len(args) == 1:
            x = args[0]
            return f"{tpl}({x})"

        if len(args) == 2:
            a0_is_int = args[0].isdigit()
            a1_is_int = args[1].isdigit()
            if a0_is_int ^ a1_is_int:  # genau eines ist Zahl
                n = int(args[0] if a0_is_int else args[1])
                x = args[1] if a0_is_int else args[0]
                if tpl == "existence" and n == 1:
                    return f"existence({x})"
                if tpl == "absence" and n == 1:
                    return f"absence({x})"
                if tpl == "exactly" and n == 1:
                    return f"exactly({x})"
                return f"{tpl}({n}, {x})"

    if tpl in _COMMUTATIVE and len(args) == 2:
        a, b = args
        if a.lower() > b.lower():
            args = [b, a]

    if len(args) == 1:
        return f"{tpl}({args[0]})"
    elif len(args) == 2:
        return f"{tpl}({args[0]}, {args[1]})"
    else:
        # Fallback if more than 2 args (schouldnt happen)
        return f"{tpl}({', '.join(args)})"

def parse_declare_set(spec: str) -> Set[str]:
    return {normalize_constraint(c) for c in split_declare(spec)}
