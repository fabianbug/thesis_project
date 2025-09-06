PROMPT_LTLF_V1 = """You translate one natural-language constraint into LTLf (Linear Temporal Logic over finite traces).

Output JSON ONLY: {"logic":"ltlf","formula":"..."} .

SYNTAX:
proper LTLf syntax will be put here later

EXAMPLES:
NL: "Whenever A happens, B must eventually happen."
JSON: {"logic":"ltlf","formula":"G(A -> F (B))"}
"""
