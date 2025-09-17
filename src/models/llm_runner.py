import time, json, os
from typing import Optional, Any, Dict
from openai import OpenAI
from groq import Groq
import google.generativeai as gemini
from src.config import OPENAI_API_KEY, GEMINI_API_KEY, GROQ_API_KEY, require

class LLMRunner:
    def __init__(self, provider: str, model: str, api_key: Optional[str] = None, temperature: float = 1.0):
        self.provider = provider.lower().strip()
        self.model, self.temperature = model, temperature

        if self.provider == "gemini" or self.provider == "google":
            key = api_key or require("GEMINI_API_KEY", GEMINI_API_KEY)
            gemini.configure(api_key=key)
            self.client = gemini.GenerativeModel(model_name=model)
        elif self.provider == "groq":
            key = api_key or require("GROQ_API_KEY", GROQ_API_KEY)
            self.client = Groq(api_key=key)
        elif self.provider == "openai" or self.provider == "chatgpt":
            key = api_key or require("OPENAI_API_KEY", OPENAI_API_KEY)
            self.client = OpenAI(api_key=key)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    # generate a response 
    def generate(self, system: str = None, user: str = None, messages: list = None, **kwargs) -> str:
    
        if messages is None:
            if system is None or user is None:
                raise ValueError("Provide either (system,user) or messages.")
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]

        if getattr(self, "provider", None) == "openai" or getattr(self, "provider", None) == "chatgpt":
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
            )
            return resp.choices[0].message.content

        # gemini is special
        elif getattr(self, "provider", None) == "gemini" or getattr(self, "provider", None) == "google":
            try:
                import google.generativeai as gemini  
            except Exception:
                pass  

            sys_prompt = next((m["content"] for m in messages if m["role"] == "system"), "")
            user_chunks = [m["content"] for m in messages if m["role"] == "user"]
            user_text = "\n\n".join(user_chunks)

            model = self.gemini_model if hasattr(self, "gemini_model") else None
            if model is None:
                model = self.gemini_factory(self.model, system_instruction=sys_prompt) \
                    if hasattr(self, "gemini_factory") else None
            if model is None:
                import google.generativeai as gemini
                model = gemini.GenerativeModel(self.model, system_instruction=sys_prompt)

            resp = model.generate_content(user_text)
            return getattr(resp, "text", str(resp))

        else:
            #fallback: concatenate system + user messages
            sys_txt = next((m["content"] for m in messages if m["role"] == "system"), "")
            usr_txt = "\n\n".join(m["content"] for m in messages if m["role"] == "user")
            prompt = (sys_txt + "\n\n" + usr_txt).strip()
            return self.client.complete(prompt)  
