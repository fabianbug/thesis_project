import re
from typing import List, Set

#this is a normalizer for declare strings so that we can compare phi and psi

# response(A,B); precedence(B,C)\nexistence(D)  -> ["response(A,B)", "precedence(B,C)", "existence(D)"]
_DEF_SPLIT = re.compile(r"[;\n]+") 
_TPL_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_\-\s]*)\s*\(\s*([^)]+)\s*\)\s*$") 


def split_declare(spec: str) -> List[str]:
    if not spec:
        return []
    parts = _DEF_SPLIT.split(spec.strip())
    return [p.strip() for p in parts if p.strip()]

def normalize_constraint(c: str) -> str:
    m = _TPL_RE.match(c)
    if not m:
        return c.strip()
    tpl = m.group(1).strip().lower().replace(" ", "-")
    args = [a.strip().replace(" ", "") for a in m.group(2).split(",")]
    return f"{tpl}({','.join(args)})"

def parse_declare_set(spec: str) -> Set[str]:
    return {normalize_constraint(c) for c in split_declare(spec)}
