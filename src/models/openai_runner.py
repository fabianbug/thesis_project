# src/models/openai_runner.py
from openai import OpenAI
from pydantic import BaseModel
from typing import Dict, Any, Optional, Tuple
import os, time, json, re

from src.config import OPENAI_API_KEY, require

class LLMResponse(BaseModel):
    logic: str
    formula: str
    raw: Dict[str, Any]
    latency_ms: int
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None

def _extract_json(text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Versucht {"logic": "...", "formula": "..."} aus der Modellantwort zu ziehen.
    - erst: JSON-Block
    - dann: Codefence ```json ... ```
    """
    
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.S)
    if m:
        try:
            obj = json.loads(m.group(1))
            return obj.get("logic"), obj.get("formula")
        except Exception:
            pass
    # if simple JSON:
    try:
        obj = json.loads(text)
        return obj.get("logic"), obj.get("formula")
    except Exception:
        pass
    
    m = re.search(r'"formula"\s*:\s*"([^"]+)"', text)
    return ("ltlf", m.group(1)) if m else (None, None)

class OpenAIModel:
    def __init__(self, model: str, api_key: Optional[str] = None, temperature: float = 0.2):
        key = api_key or require("OPENAI_API_KEY", OPENAI_API_KEY)
        self.client = OpenAI(api_key=key)
        self.model = model
        self.temperature = temperature

    def generate(self, system_prompt: str, nl_spec: str) -> LLMResponse:
        """
        Expects: model returns JSON like:
        {"logic":"ltlf","formula":"G(A -> F B)"}
        """
        t0 = time.time()
        r = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            response_format={"type": "json_object"},  # JSON only
            messages=[
                {"role": "system", "content": (
                    "Convert the user's constraint to LTLf (finite-trace). "
                    "Return ONLY a JSON object: {\"logic\":\"ltlf\",\"formula\":\"...\"}. "
                    "Use operators like G,F,X,U and !,&,|,-> with parentheses as needed."
                )},
                {"role": "user", "content": nl_spec},
            ],
        )
        dt = int((time.time() - t0) * 1000)
        text = r.choices[0].message.content or ""

        logic, formula = _extract_json(text)
        if not (logic and formula):
            # Fallback: gives out plain text so nothing gets lost
            logic, formula = "ltlf", text.strip()

        usage = getattr(r, "usage", None)
        tokens_in = getattr(usage, "prompt_tokens", None) if usage else None
        tokens_out = getattr(usage, "completion_tokens", None) if usage else None

        return LLMResponse(
            logic=logic,
            formula=formula,
            raw=r.model_dump(),     # full raw stuff
            latency_ms=dt,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
