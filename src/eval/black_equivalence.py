# TODO: hier später BLACK anbinden und echte Äquivalenz prüfen
def is_parseable_ltlf(formula: str) -> bool:
    return isinstance(formula, str) and len(formula) > 0
