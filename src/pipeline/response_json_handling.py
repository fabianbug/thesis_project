from pydantic import BaseModel
from typing import Dict, Any, Optional, Tuple, List
import os, time, json, re

# define exports:
__all__ = ["LLMResponse", "_extract_json"]

class LLMResponse(BaseModel):
    declare: List[Dict[str, Any]]
    raw: Dict[str, Any]
    latency_ms: int
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None

def _extract_json(text: str) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """
    gets declare from LLM answer text
    Expected schema:
    {"declare":[{"template":"...","args":[...]}]}
    """
    # 1) Codefence 
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.S)
    if m:
        try:
            obj = json.loads(m.group(1))
            declare = obj.get("declare", [])
            if not isinstance(declare, list):
                declare = []
            return declare
        except Exception:
            pass

    # 2) straight JSON
    try:
        obj = json.loads(text)
        declare = obj.get("declare", [])
        if not isinstance(declare, list):
            declare = []
        return declare
    except Exception:
        pass

    # 3) Fallback: regex
    m_declare = re.search(r'"declare"\s*:\s*(\[[^\]]*\])', text)
    if m_declare:
        return json.loads(m_declare.group(1)), []
    return (None, [])