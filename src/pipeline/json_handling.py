from pydantic import BaseModel
from typing import Dict, Any, Optional, Tuple, List
import os, time, json, re

# define exports:
__all__ = ["LLMResponse", "_extract_json"]

class LLMResponse(BaseModel):
    ltlf: str
    declare: List[Dict[str, Any]]
    raw: Dict[str, Any]
    latency_ms: int
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None

def _extract_json(text: str) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """
    gets ltlf + declare from LLM answer text
    Expected schema:
    {"ltlf":"<...>", "declare":[{"template":"...","args":[...]}]}
    Backward-Compat:
    {"logic":"ltlf","formula":"<...>"} -> ltlf = formula, declare=[]
    Fallbacks (if LLM fails to follow my instructions):
        simple regex on "ltlf" or "formula"
    """
    # 1) Codefence 
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.S)
    if m:
        try:
            obj = json.loads(m.group(1))
            ltlf = obj.get("ltlf")
            declare = obj.get("declare", [])
            if ltlf is None and isinstance(obj.get("formula"), str):
                ltlf = obj["formula"]
            if not isinstance(declare, list):
                declare = []
            return ltlf, declare
        except Exception:
            pass

    # 2) Direkter JSON
    try:
        obj = json.loads(text)
        ltlf = obj.get("ltlf")
        declare = obj.get("declare", [])
        if ltlf is None and isinstance(obj.get("formula"), str):
            ltlf = obj["formula"]
        if not isinstance(declare, list):
            declare = []
        return ltlf, declare
    except Exception:
        pass

    # 3) Fallback: regex
    m_ltlf = re.search(r'"ltlf"\s*:\s*"([^"]+)"', text)
    if m_ltlf:
        return m_ltlf.group(1), []
    m_formula = re.search(r'"formula"\s*:\s*"([^"]+)"', text)
    if m_formula:
        return m_formula.group(1), []
    return (None, [])