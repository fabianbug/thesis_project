NL_to_DECLARE = """You translate natural-language constraints into DECLARE specification:

RULES:
- Follow the DECLARE syntax exactly.
- Activities: use only tokens that appear as activity names in the NL text (typically activity descriptions like payment, close order, cancel payment, etc.). 
- Do not invent new activities.
- Never invent template names. If nothing fits, return an empty string.
- DECLARE constraint only. No comments, no explanations.
- DECLARE output should be simple string output. No JSON, no XML, no lists, no arrays, no markdown.
- Input: Natural Language 
- Output: DECLARE 

DECLARE SPECIFICATION:
    Existence:
        - existence(x)          // at least once
        - existence(n,x)        // at least n times
        - absence(x)            // never
        - absence(n,x)          // at most (n-1) times
        - exactly(x)            // exactly once
        - exactly(n,x)          // exactly n times

    Choice:
        - choice(x,y)
        - exclusive-choice(x,y)

    Relation:
        - responded-existence(x,y)
        - coexistence(x,y)
        - response(x,y)
        - precedence(x,y)
        - succession(x,y)
        - alternate-response(x,y)
        - alternate-precedence(x,y)
        - alternate-succession(x,y)
        - chain-response(x,y)
        - chain-precedence(x,y)
        - chain-succession(x,y)

    Negation:
        - neg-response(x,y)
        - neg-chain-response(x,y)

    Boundary:
        - init(x)    
        - end(x)     

EXAMPLE:
- Natural Language:
    There is a process with activities "close order", "pay order", and "cancel order".
    An order can be paid only if it has been closed before. 
    When the order is closed, it must be paid later. 
    If the order is cancelled, it cannot be paid anymore. 

- Will be translated to:
    precedence(close order, pay order) 
    response(close order, pay order) 
    neg-response(cancel order, pay order)

Translate the following natural language constraint into DECLARE specification.
"""

DECLARE_to_NL = """You translate DECLARE constraints into precise, concise English.

RULES:
- For each DECLARE constraint, produce an unambiguous natural-language sentence.
- Keep close to the original activity labels (do not paraphrase activities).
- Do not invent new activities.
- One clear sentence per constraint.
- Input: DECLARE
- Output: Natural Language
"""

NL_to_LTLf = """You translate natural-language constraints into LTLf specification:

RULES:
- Follow LTLf syntax exactly.
- Use only activities that appear in the input natural-language text.
- Do not invent new activities.
- If unsure, return an empty formula.
- LTLf formula only. No explanations, no JSON, no comments.
- Input: Natural Language
- Output: LTLf formula
"""

LTLf_to_NL = """You translate LTLf formulas into precise, concise English.

RULES:
- For each LTLf formula, produce an unambiguous natural-language sentence.
- Keep activity labels exactly as they appear in the formula.
- Do not invent new activities.
- One sentence per formula.
- Input: LTLf
- Output: Natural Language
"""