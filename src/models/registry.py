from __future__ import annotations
from typing import Any

from src.models.openai_runner import OpenAIModel

def create_runner(provider: str, model: str, temperature: float = 0.2, **kwargs: Any):
    
    p = (provider or "openai").lower()
    if p == "openai":
        return OpenAIModel(model=model, temperature=temperature, **kwargs)
    raise ValueError(f"Unknown provider: {provider}")
