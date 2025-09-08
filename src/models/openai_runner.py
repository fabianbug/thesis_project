import time, json
from typing import Optional
from openai import OpenAI

from src.config import OPENAI_API_KEY, require
from pipeline.response_json_handling import LLMResponse, _extract_json

class OpenAIModel:
    def __init__(self, model: str, api_key: Optional[str] = None, temperature: float = 1.0):
        key = api_key or require("OPENAI_API_KEY", OPENAI_API_KEY)
        self.client = OpenAI(api_key=key)
        self.model = model
        self.temperature = temperature


    # generate a response and parse it into LLMResponse 
    def generate(self, system_prompt: str, nl_spec: str) -> LLMResponse:
        
        t0 = time.time()
        r = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            response_format={"type": "json_object"},  # ensure JSON 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": nl_spec},
            ],
        )
        dt = int((time.time() - t0) * 1000)
        text = r.choices[0].message.content or ""

        ltlf, declare = _extract_json(text)
        if not ltlf:
            # Fallback: get text as ltlf and leave declare empty
            ltlf, declare = text.strip(), []

        usage = getattr(r, "usage", None)
        tokens_in = getattr(usage, "prompt_tokens", None) if usage else None
        tokens_out = getattr(usage, "completion_tokens", None) if usage else None




        # raw 
        try:
            raw_obj = r.model_dump()
        except Exception:
            try:
                raw_obj = json.loads(r.model_dump_json()) if hasattr(r, "json") else {"raw": str(r)}
            except Exception:
                raw_obj = {"raw": str(r)}

        return LLMResponse(
            ltlf=ltlf,
            declare=declare,
            raw=raw_obj,
            latency_ms=dt,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
