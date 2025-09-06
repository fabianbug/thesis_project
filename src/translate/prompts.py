PROMPT_LTLF_V1 = """You translate one natural-language constraint into LTLf (Linear Temporal Logic over finite traces).

Output JSON ONLY: {"logic":"ltlf","formula":"..."}  — no notes, no prose.

SYNTAX:
- Temporal ops: G, F, X, U
- Boolean: !, &, |, ->
- Parentheses required to disambiguate: use plenty of ( )
- Atomic propositions are activity labels (A, B, approve_invoice, ...).
- No past-time operators. No CTL/MTL. No natural language.

EXAMPLES:
NL: "Whenever A happens, B must eventually happen."
JSON: {"logic":"ltlf","formula":"G(A -> F (B))"}
"""
