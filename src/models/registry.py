from __future__ import annotations
from typing import Any

from src.models.llm_runner import LLMRunner

def create_runner(provider: str, model: str, temperature: float = 1.0, **kwargs: Any):
    return LLMRunner(provider=provider, model=model, temperature=temperature, **kwargs)
