from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Dict, List, Callable, Any

# AP sanitization
_AP_SAFE = re.compile(r"[^A-Za-z0-9_]")
def sanitize_ap(name: str) -> str:
    core = name.strip().lower().replace(" ", "_")
    core = _AP_SAFE.sub("_", core)
    prefix = core[0].upper() if core else "A"
    return f"{prefix}_{core}"

# LTLf helpers
def X(phi: str) -> str:                 return f"X({phi})"
def F(phi: str) -> str:                 return f"F({phi})"
def G(phi: str) -> str:                 return f"G({phi})"
def U(a: str, b: str) -> str:           return f"(({a}) U ({b}))"
def Not(phi: str) -> str:               return f"!({phi})"
def And(*args: str) -> str:             return " & ".join(f"({a})" for a in args if a)
def Or(*args: str) -> str:              return " | ".join(f"({a})" for a in args if a)
def Implies(a: str, b: str) -> str:     return f"({a} -> {b})"
def Iff(a: str, b: str) -> str:         return And(Implies(a,b), Implies(b,a))
def True_() -> str:                     return "true"
def Last() -> str:                      return Not(X(True_()))  # ¬X true  — standard LTLf encoding
def Xw(phi: str) -> str:                return Or(X(phi), Last())  # weak-next via X + Last

# Template encodings for LTLf
def _resp(a, b):            return G(Implies(a, F(b)))                       # response(a,b)
def _prec(a, b):            return Or(U(Not(b), a), G(Not(b)))               # precedence(a,b)
def _succ(a, b):            return And(_resp(a,b), _prec(a,b))               # succession(a,b)
def _chain_resp(a, b):      return G(Implies(a, X(b)))                       # chain-response(a,b)
def _exist(a):              return F(a)                                      # existence(a)
def _absence(a):            return G(Not(a))                                 # absence(a)
def _exactly1(a):           return And(F(a), Not(F(And(a, F(a)))))           # exactly(a) ~ exactly 1
def _resp_exist(a, b):      return Implies(F(a), F(b))                        # responded-existence(a,b)
def _coexist(a, b):         return And(_resp_exist(a,b), _resp_exist(b,a))    # coexistence(a,b)
def _choice(a, b):          return Or(F(a), F(b))                             # choice(a,b)
def _excl_choice(a, b):     return And(_choice(a,b), Not(And(F(a), F(b))))    # exclusive-choice(a,b)
def _neg_resp(a, b):        return G(Implies(a, Not(F(b))))                   # neg-response(a,b)
def _not_succ(a, b):        return _neg_resp(a, b)                            # not-succession(a,b)
def _neg_chain_resp(a, b):  return G(Implies(a, Not(X(b))))                   # neg-chain-response(a,b)
def _init(a):               return a                                          # init(a): hold at pos 0
def _end(a):                return F(f"({a}) & {Last()}")                                     # end(a): occurs at some final pos

def _is_int(s: str) -> bool:
    try:
        int(s); return True
    except Exception:
        return False
    
# Aliases 
ALIASES: Dict[str, str] = {
    # existence family
    "existence": "existence",
    "absence": "absence",
    "exactly": "exactly",
    "at-most-one": "absence",      # treat as absence(1)
    "at_most_one": "absence",
    "atleastone": "existence",
    "at-least-one": "existence",
    "at_least_one": "existence",

    # choice family
    "choice": "choice",
    "exclusive-choice": "exclusive-choice",
    "exclusive_choice": "exclusive-choice",

    # relation family
    "responded-existence": "responded-existence",
    "responded_existence": "responded-existence",
    "coexistence": "coexistence",
    "response": "response",
    "precedence": "precedence",
    "succession": "succession",
    "alternate-response": "alternate-response",
    "alternate_response": "alternate-response",
    "alternate-precedence": "alternate-precedence",
    "alternate_precedence": "alternate-precedence",
    "alternate-succession": "alternate-succession",
    "alternate_succession": "alternate-succession",
    "chain-response": "chain-response",
    "chain_response": "chain-response",
    "chain-precedence": "chain-precedence",
    "chain_precedence": "chain-precedence",
    "chain-succession": "chain-succession",
    "chain_succession": "chain-succession",

    # negative family
    "neg-response": "neg-response",
    "neg_response": "neg-response",
    "not-response": "neg-response",
    "not_response": "neg-response",

    "not-responded-existence": "not-responded-existence",
    "not_responded_existence": "not-responded-existence",
    "neg-responded-existence": "not-responded-existence",
    "neg_responded_existence": "not-responded-existence",

    "not-chain-response": "not-chain-response",
    "not_chain_response": "not-chain-response",
    "neg-chain-response": "not-chain-response",
    "neg_chain_response": "not-chain-response",

    "not-succession": "neg-succession",
    "non-succession": "neg-succession",
    "not_succession": "neg-succession",
    "non_succession": "neg-succession",

    "not-precedence": "not-precedence",
    "not_precedence": "not-precedence",
    "neg-precedence": "not-precedence",
    "neg_precedence": "not-precedence",

    "not-chain-precedence": "not-chain-precedence",
    "not_chain_precedence": "not-chain-precedence",
    "neg-chain-precedence": "not-chain-precedence",
    "neg_chain_precedence": "not-chain-precedence",

    "neg-chain-response": "neg-chain-response",
    "not-chain-response": "neg-chain-response",
    "neg_chain_response": "neg-chain-response",
    "not_chain_response": "neg-chain-response",

    "not-coexistence": "not-coexistence",
    "not_coexistence": "not-coexistence",

    # boundaries
    "init": "init",
    "start": "init",
    "end": "end",
    "finish": "end",
}

# Dispatcher
TEMPLATES: Dict[str, Callable[..., str]] = {
    "existence": lambda x: _exist(x),                        
    "absence":   lambda x, n=1: _absence(x, n),             
    "exactly":   lambda x, n=1: _exactly1(x, n),              

    "choice":              lambda x, y: _choice(x, y),
    "exclusive-choice":    lambda x, y: _excl_choice(x, y),

    "responded-existence": lambda x, y: _resp_exist(x, y),
    "coexistence":         lambda x, y: _coexist(x, y),
    "response":            lambda x, y: _resp(x, y),
    "precedence":          lambda x, y: _prec(x, y),
    "succession":          lambda x, y: _succ(x, y),
    "alternate-response":  lambda x, y: G(Implies(x, X(U(Not(x), y)))),  # G(x -> X(!x U y))
    "alternate-precedence":lambda x, y: Or(U(Not(y), X(x)), G(Not(y))),   # (true U (!y X x)) & G(!y)
    "alternate-succession":lambda x, y: And(
                                    G(Implies(x, X(U(Not(x), y)))),  # G(x -> X(!x U y))
                                    Or(U(Not(y), X(x)), G(Not(y)))    # (true U (!y X x)) & G(!y)
                                ),
    "chain-precedence":    lambda x, y: Or(U(Not(y), X(x)), G(Not(y))),   # (true U (!y X x)) & G(!y)

    "chain-response":      lambda x, y: _chain_resp(x, y),

    "neg-response":        lambda x, y: _neg_resp(x, y),

    "not-chain-response":      lambda x, y: G(Implies(x, Not(X(y)))), # G(x -> !X y)

    "not-responded-existence": lambda x, y: Implies(F(x), Not(F(y))),

    "not-precedence":          lambda x, y: G(Implies(y, H(Not(x)))),   # G(y -> H ¬x)

    "not-chain-precedence":    lambda x, y: G(Implies(y, Not(Y(x)))),   # G(y -> ¬Y x)


    "neg-succession":      lambda x, y: _not_succ(x, y),
    "neg-chain-response":  lambda x, y: _neg_chain_resp(x, y),

    "not-coexistence":     lambda x, y: Not(And(F(x), F(y))),

    "init":                lambda x: _init(x),
    "end":                 lambda x: _end(x),
}

def _canon_template(name: str) -> str:
    n = name.strip().lower().replace(" ", "-")
    return ALIASES.get(n, n)



# Parsing DECLARE strings
_DECL_RE = re.compile(r"\s*([A-Za-z][A-Za-z0-9_\-\s]*)\s*\(\s*([^)]+)\s*\)\s*$")

def split_declare_constraints(declare_str: str) -> List[str]:
    parts = re.split(r"[;\n]+", declare_str.strip())
    return [p.strip() for p in parts if p.strip()]

def parse_declare_string(spec: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for raw in split_declare_constraints(spec):
        m = _DECL_RE.match(raw)
        if not m:
            raise ValueError(f"Unrecognized DECLARE constraint: {raw}")
        templ = m.group(1).strip()
        args = [a.strip() for a in m.group(2).split(",")]
        items.append({"template": templ, "args": args})
    return items




# Public APIs
@dataclass
class EncodeResult:
    formula: str                  # single LTLf formula (conjunction)
    per_constraint: List[str]     # LTLf per constraint
    ap_map: Dict[str, str]        # original label -> AP

def declare_string_to_ltlf(spec: str) -> str: #return only the single LTLf formula
    return declare_string_to_ltlf_with_map(spec).formula

def declare_string_to_ltlf_with_map(spec: str) -> EncodeResult:
    parsed = parse_declare_string(spec)

    # collect activities for stable AP map
    acts: List[str] = []
    for c in parsed:
        for a in c["args"]:
            if a not in acts:
                acts.append(a)
    ap_map = {a: sanitize_ap(a) for a in acts}

    per: List[str] = []
    for c in parsed:
        tpl = ALIASES.get(c["template"].lower(), c["template"].lower())
        args_raw = [a.strip() for a in c["args"]]

        def _map_ap(a: str) -> str:
            return ap_map.get(a, sanitize_ap(a))

        args_map = [_map_ap(a) for a in args_raw]

        if tpl in ("exactly", "absence") and len(args_raw) == 2 and (_is_int(args_raw[0]) or _is_int(args_raw[1])):
            if _is_int(args_raw[0]):
                n = int(args_raw[0]); x = args_map[1]
            else:
                n = int(args_raw[1]); x = args_map[0]
            per.append(TEMPLATES[tpl](x, n))   # <-- per, nicht formulas
            continue

        if tpl not in TEMPLATES:
            raise ValueError(f"Unsupported/unknown DECLARE template: {c['template']!r} (normalized: {tpl})")

        fn = TEMPLATES[tpl]
        
        if len(args_map) == 1:
            per.append(fn(args_map[0]))
        elif len(args_map) == 2:
            per.append(fn(args_map[0], args_map[1]))
        else:
            raise ValueError(f"Template {tpl} requires 1 or 2 args, got {len(args_map)}")

    formula = And(*per) if per else "true"
    return EncodeResult(formula=formula, per_constraint=per, ap_map=ap_map)

# Quick test 
if __name__ == "__main__":
    decl = "precedence(close order, pay order) \nresponse(close order, pay order) \nnegation-response(cancel order, pay order)"
    res = declare_string_to_ltlf_with_map(decl)
    print("AP map:", res.ap_map)
    print("LTLf per constraint:")
    for i, f in enumerate(res.per_constraint, 1):
        print(f"  [{i}] {f}")
    print("Conjunction:\n", res.formula)
