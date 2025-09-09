from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple, Callable, Any
import re, json, subprocess, tempfile, shlex



_AP_SAFE = re.compile(r"[^A-Za-z0-9_]")


def sanitize_ap(name: str) -> str:
    """
    Turn an activity label like 'close order' into a valid atomic proposition, e.g. A_close_order.
    - Keep it deterministic and reversible via the returned map.
    """
    core = name.strip().lower().replace(" ", "_")
    core = _AP_SAFE.sub("_", core)
    return f"A_{core}"


@dataclass
class TranslateResult:
    ltlf: str                 # full LTLf formula (conjunction of constraints)
    constraints_ltlf: List[str]  # each constraint's LTLf
    ap_map: Dict[str, str]    # original activity -> AP identifier (for debugging/trace explanations)


# LTLf helpers
def X(phi: str) -> str:  return f"X({phi})"
def F(phi: str) -> str:  return f"F({phi})"
def G(phi: str) -> str:  return f"G({phi})"
def U(phi1: str, phi2: str) -> str: return f"({phi1}) U ({phi2})"
def Not(phi: str) -> str: return f"¬({phi})"
def And(*args: str) -> str: return " ∧ ".join(f"({a})" for a in args)
def Or(*args: str) -> str:  return " ∨ ".join(f"({a})" for a in args)
def Implies(a: str, b: str) -> str: return Or(Not(a), b)
def Iff(a: str, b: str) -> str: return And(Implies(a,b), Implies(b,a))
def True_() -> str: return "true"
def Last() -> str: return Not(X(True_()))  # ¬X true  — standard LTLf encoding
def Xw(phi: str) -> str: return Or(X(phi), Last())  # weak-next via X + Last


# ========== DECLARE → LTLf template mapping ==========

# Canonical template keys (lowercase, hyphenated)
# We support common aliases to be resilient to small naming differences.
ALIASES: Dict[str, str] = {
    # existence class
    "existence": "existence",
    "existence(1)": "existence",
    "absence": "absence",
    "exactly": "exactly",
    "at-most-one": "at-most-one",
    "at_most_one": "at-most-one",
    "atleastone": "existence",
    "at-least-one": "existence",
    "at_least_one": "existence",
    # choice
    "choice": "choice",
    "exclusive-choice": "exclusive-choice",
    "exclusive_choice": "exclusive-choice",
    # relation
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
    # negation family (common names seen in papers/repos)
    "neg-response": "neg-response",
    "negation-response": "neg-response",
    "not-response": "neg-response",
    "neg-chain-response": "neg-chain-response",
    "negation-chain-response": "neg-chain-response",
    "not-chain-response": "neg-chain-response",
    "not-succession": "not-succession",
    "non-succession": "not-succession",
    "not_chain_succession": "not-chain-succession",
    "not-chain-succession": "not-chain-succession",
    # sometimes used:
    "not-coexistence": "not-coexistence",
    "non-coexistence": "not-coexistence",
    # boundary templates
    "init": "init",
    "start": "init",
    "end": "end",
    "finish": "end",
}

# Implementations:
# NOTE: I stick to standard LTLf operators {G,F,X,U,¬,∧,∨} only.
# Where literature uses Xw, we emit Xw via (X φ) ∨ Last().
def _tpl_existence(x: str) -> str:
    return F(x)

def _tpl_absence(x: str) -> str:
    return Not(F(x))  # ¬F x

def _tpl_exactly(x: str, n: int = 1) -> str:
    # For exactly(1, x) ≡ existence(x) ∧ absence(2, x)
    # We provide n=1 now; extend if you later need counts >1 (requires counters).
    return And(F(x), Not(F(And(x, F(x)))))  # crude finite-trace proxy for "at most once"
    # For production, implement a counter-based automaton or LDLf; for now keep n=1 scope.

def _tpl_choice(x: str, y: str) -> str:
    return Or(F(x), F(y))

def _tpl_exclusive_choice(x: str, y: str) -> str:
    # choice(x,y) ∧ ¬(F(x) ∧ F(y))
    return And(Or(F(x), F(y)), Not(And(F(x), F(y))))

def _tpl_responded_existence(x: str, y: str) -> str:
    return Implies(F(x), F(y))  # F x -> F y

def _tpl_coexistence(x: str, y: str) -> str:
    return And(Implies(F(x), F(y)), Implies(F(y), F(x)))

def _tpl_response(x: str, y: str) -> str:
    return G(Implies(x, F(y)))  # G (x -> F y)

def _tpl_precedence(x: str, y: str) -> str:
    # (¬y U x) ∨ G(¬y)
    return Or(U(Not(y), x), G(Not(y)))

def _tpl_succession(x: str, y: str) -> str:
    # response(x,y) ∧ precedence(x,y)
    return And(_tpl_response(x, y), _tpl_precedence(x, y))

def _tpl_alt_response(x: str, y: str) -> str:
    # G (x -> X(¬x U y))
    return G(Implies(x, X(U(Not(x), y))))

def _tpl_alt_precedence(x: str, y: str) -> str:
    # precedence(x,y) ∧ G(y -> Xw(precedence(x,y)))
    return And(
        _tpl_precedence(x, y),
        G(Implies(y, Xw(_tpl_precedence(x, y))))
    )

def _tpl_alt_succession(x: str, y: str) -> str:
    return And(_tpl_alt_response(x, y), _tpl_alt_precedence(x, y))

def _tpl_chain_response(x: str, y: str) -> str:
    return G(Implies(x, X(y)))  # immediate next

def _tpl_chain_precedence(x: str, y: str) -> str:
    # G(X y -> x) ∧ ¬y (at position 0)
    # A common finite-trace encoding seen in literature tables:
    return And(G(Implies(X(y), x)), Not(y))

def _tpl_chain_succession(x: str, y: str) -> str:
    return And(_tpl_chain_response(x, y), _tpl_chain_precedence(x, y))

def _tpl_neg_response(x: str, y: str) -> str:
    # G (x -> ¬F y)
    return G(Implies(x, Not(F(y))))

def _tpl_neg_chain_response(x: str, y: str) -> str:
    # G (x -> ¬X y)
    return G(Implies(x, Not(X(y))))

def _tpl_not_coexistence(x: str, y: str) -> str:
    return Not(And(F(x), F(y)))


def _tpl_init(x: str) -> str:
    # Init(x): x must hold at the first position (we evaluate at position 0)
    return x

def _tpl_end(x: str) -> str:
    # End(x): x must hold at the last position
    return F(And(Last(), x))

def _tpl_at_most_one(x: str) -> str:
    # AtMostOne(x): x occurs at most once
    # Equivalent to: not (exists two distinct positions with x), encoded as: ¬F(x ∧ F(x))
    return Not(F(And(x, F(x))))

def _tpl_not_succession(x: str, y: str) -> str:
    # Not-Succession(x,y): if x occurs, then y cannot occur afterwards
    # Note: This equals our "neg-response" semantics in common Declare repertoires
    return G(Implies(x, Not(F(y))))

def _tpl_not_chain_succession(x: str, y: str) -> str:
    # Not-Chain-Succession(x,y): y must not occur immediately after x
    return G(Implies(x, Not(X(y))))



# Registry of callable constructors
TEMPLATES: Dict[str, Callable[..., str]] = {
    # Existence family (only n=1 explicitly supported here)
    "existence": lambda x: _tpl_existence(x),
    "absence":   lambda x: _tpl_absence(x),
    "exactly":   lambda x: _tpl_exactly(x, 1),

    # Choice
    "choice":             lambda x, y: _tpl_choice(x, y),
    "exclusive-choice":   lambda x, y: _tpl_exclusive_choice(x, y),

    # Relations
    "responded-existence": lambda x, y: _tpl_responded_existence(x, y),
    "coexistence":         lambda x, y: _tpl_coexistence(x, y),
    "response":            lambda x, y: _tpl_response(x, y),
    "precedence":          lambda x, y: _tpl_precedence(x, y),
    "succession":          lambda x, y: _tpl_succession(x, y),

    "alternate-response":    lambda x, y: _tpl_alt_response(x, y),
    "alternate-precedence":  lambda x, y: _tpl_alt_precedence(x, y),
    "alternate-succession":  lambda x, y: _tpl_alt_succession(x, y),

    "chain-response":    lambda x, y: _tpl_chain_response(x, y),
    "chain-precedence":  lambda x, y: _tpl_chain_precedence(x, y),
    "chain-succession":  lambda x, y: _tpl_chain_succession(x, y),

    # Negation family
    "neg-response":         lambda x, y: _tpl_neg_response(x, y),
    "neg-chain-response":   lambda x, y: _tpl_neg_chain_response(x, y),

    # sometimes used
    "not-coexistence":      lambda x, y: _tpl_not_coexistence(x, y),

        # Boundary templates
    "init":            lambda x: _tpl_init(x),
    "end":             lambda x: _tpl_end(x),

    # Existence variant
    "at-most-one":     lambda x: _tpl_at_most_one(x),

    # Negative succession family
    "not-succession":        lambda x, y: _tpl_not_succession(x, y),
    "not-chain-succession":  lambda x, y: _tpl_not_chain_succession(x, y),

}


def _canon_template(name: str) -> str:
    n = name.strip().lower().replace(" ", "-")
    return ALIASES.get(n, n)


# ========== Public API ==========

def translate_declare_constraints(declare_list: List[Dict[str, Any]]) -> TranslateResult:
    """
    Input: [{"template": "response", "args": ["close order", "pay order"]}, ...]
    Output: LTLf for the conjunction of all constraints + per-constraint list + AP map.
    """
    # First pass: collect all activity labels to build a stable AP map
    activities: List[str] = []
    for c in declare_list:
        args = c.get("args", [])
        for a in args:
            if isinstance(a, str) and a not in activities:
                activities.append(a)

    ap_map: Dict[str, str] = {a: sanitize_ap(a) for a in activities}
    constraints_ltlf: List[str] = []

    for c in declare_list:
        tpl_raw = c.get("template", "")
        tpl = _canon_template(tpl_raw)
        if tpl not in TEMPLATES:
            raise ValueError(f"Unsupported/unknown DECLARE template: {tpl_raw!r} (normalized: {tpl})")

        args = c.get("args", [])
        # Map activity labels to AP identifiers
        ap_args: List[str] = [ap_map.get(a, sanitize_ap(str(a))) for a in args]

        # Arity checking (1 or 2)
        fn = TEMPLATES[tpl]
        try:
            if len(ap_args) == 1:
                ltlf = fn(ap_args[0])  # existence/absence/exactly
            elif len(ap_args) == 2:
                ltlf = fn(ap_args[0], ap_args[1])  # binary templates
            else:
                raise ValueError(f"Template {tpl} requires 1 or 2 args, got {len(ap_args)}")
        except TypeError as e:
            raise ValueError(f"Template {tpl} arity mismatch: {e}")

        constraints_ltlf.append(ltlf)

    full = And(*constraints_ltlf) if constraints_ltlf else True_()
    return TranslateResult(ltlf=full, constraints_ltlf=constraints_ltlf, ap_map=ap_map)


def translate_phi_json(phi_obj: Dict[str, Any]) -> TranslateResult:
    """
    Expects: {"declare": [ ...constraints... ]} as in your testcases.
    """
    if "declare" not in phi_obj or not isinstance(phi_obj["declare"], list):
        raise ValueError("phi_obj must contain key 'declare' with a list of constraints.")
    return translate_declare_constraints(phi_obj["declare"])


def translate_psi_json(psi_obj: Dict[str, Any]) -> TranslateResult:
    """
    Same structure as phi: a DECLARE JSON from the LLM response (after you've parsed/validated it).
    """
    if "declare" not in psi_obj or not isinstance(psi_obj["declare"], list):
        raise ValueError("psi_obj must contain key 'declare' with a list of constraints.")
    return translate_declare_constraints(psi_obj["declare"])


# ========== BLACK equivalence (stub) ==========

def build_biimplication(phi_ltlf: str, psi_ltlf: str) -> str:
    """
    Compose a bi-implication formula φ ↔ ψ for equivalence checking.
    """
    return Iff(phi_ltlf, psi_ltlf)


def _black_check_valid(ltlf_formula: str) -> bool:
    """
    Returns True iff the LTLf formula is valid (tautology).
    Adjust the command to BLACK's CLI on your system.
    """
    # Example CLI pattern (adapt to your installation):
    # black --logic ltlf --mode valid "<formula>"
    cmd = f'black --logic ltlf --mode valid {shlex.quote(ltlf_formula)}'
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"BLACK valid failed: {res.stderr.strip() or res.stdout.strip()}")
    # Assume BLACK prints "VALID" / "NOT VALID" (adapt if different)
    return "VALID" in res.stdout.upper()

def _black_find_model(ltlf_formula: str) -> str | None:
    """
    Try to get a witness trace that satisfies the formula (if any).
    Returns a textual model/trace or None if UNSAT.
    """
    # Example CLI pattern (adapt to your installation):
    # black --logic ltlf --mode sat "<formula>"
    cmd = f'black --logic ltlf --mode sat {shlex.quote(ltlf_formula)}'
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"BLACK sat failed: {res.stderr.strip() or res.stdout.strip()}")
    out = res.stdout.upper()
    if "UNSAT" in out:
        return None
    # Otherwise return raw witness (you can parse/pretty-print later)
    return res.stdout.strip()

def check_equivalence_with_black(phi_ltlf: str, psi_ltlf: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Use BLACK to check equivalence on finite traces.
    - First: valid(Iff(phi, psi))
    - If not valid: try witnesses for phi ∧ ¬psi and psi ∧ ¬phi
    """
    biimp = build_biimplication(phi_ltlf, psi_ltlf)
    try:
        if _black_check_valid(biimp):
            return True, {}
        # Not equivalent: 
        w1 = _black_find_model(And(phi_ltlf, Not(psi_ltlf)))
        w2 = _black_find_model(And(psi_ltlf, Not(phi_ltlf)))
        info = {}
        if w1: info["phi_and_not_psi"] = w1
        if w2: info["psi_and_not_phi"] = w2
        return False, info
    except Exception as e:
        raise RuntimeError(f"BLACK integration error: {e}")


# ========== Quick manual test ==========

if __name__ == "__main__":
    # Example from your README text
    raw = """
    {"declare":[
        {"template":"response","args":["close order","pay order"]},
        {"template":"precedence","args":["close order","pay order"]},
        {"template":"negation-response","args":["cancel order","pay order"]}
    ]}
    """.strip()
    phi = json.loads(raw)
    res = translate_phi_json(phi)
    print("AP map:", res.ap_map)
    print("\nConstraints (LTLf):")
    for i, f in enumerate(res.constraints_ltlf, 1):
        print(f"  [{i}] {f}")
    print("\nPHI (conjunction):")
    print(res.ltlf)
    # just testing if it works
    tests = [
    ("response(a,b)", [{"template":"response","args":["A","B"]}],
     "G (A_a -> F(B_b))"),
    ("precedence(a,b)", [{"template":"precedence","args":["A","B"]}],
     "(¬(B_b)) U (A_a) ∨ G(¬(B_b))"),
    ("chain-response(a,b)", [{"template":"chain-response","args":["A","B"]}],
     "G (A_a -> X(B_b))"),
    ("not-succession(a,b)", [{"template":"not-succession","args":["A","B"]}],
     "G (A_a -> ¬F(B_b))"),
    ("end(a)", [{"template":"end","args":["A"]}],
     "F((¬X(true)) ∧ (A_a))"),
    ]
    for name, decl, expected_sub in tests:
        rr = translate_declare_constraints(decl)
        assert expected_sub.replace(" ", "") in rr.ltlf.replace(" ", ""), f"{name} mismatch: {rr.ltlf}"
    print("Template smoke tests passed.")
