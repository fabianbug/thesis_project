import time, json, os
from typing import Optional, Any, Dict
from openai import OpenAI
from groq import Groq
import google.generativeai as gemini
from src.config import OPENAI_API_KEY, GEMINI_API_KEY, GROQ_API_KEY, require
from src.pipeline.response_json_handling import LLMResponse, _extract_json

class LLMRunner:
    def __init__(self, provider: str, model: str, api_key: Optional[str] = None, temperature: float = 1.0):
        self.provider = provider.lower().strip()
        self.model, self.temperature = model, temperature

        if self.provider == "gemini":
            key = api_key or require("GEMINI_API_KEY", GEMINI_API_KEY)
            gemini.configure(api_key=key)
            self.client = gemini.GenerativeModel(model_name=model)
        elif self.provider == "groq":
            key = api_key or require("GROQ_API_KEY", GROQ_API_KEY)
            self.client = Groq(api_key=key)
        elif self.provider == "openai":
            key = api_key or require("OPENAI_API_KEY", OPENAI_API_KEY)
            self.client = OpenAI(api_key=key)
        else:
            raise ValueError(f"Unknown provider: {provider}")

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

        declare = _extract_json(text)
        if not declare:
            # Fallback: get text as declare and leave declare empty
            declare = text.strip(), []

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
            declare=declare,
            raw=raw_obj,
            latency_ms=dt,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
