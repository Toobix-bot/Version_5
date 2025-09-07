from __future__ import annotations
import os
import httpx
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1/chat/completions")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_MODELS_RAW = os.getenv(
    "GROQ_MODELS",
    "llama-3.1-8b-instant,llama-3.1-70b-versatile,mixtral-8x7b-32768"
)
GROQ_MODELS = [m.strip() for m in GROQ_MODELS_RAW.split(',') if m.strip()]
TIMEOUT = float(os.getenv("GROQ_TIMEOUT", "30"))
MAX_RETRIES = int(os.getenv("GROQ_RETRIES", "2"))

MODEL_HINTS = {
    "llama-3.1-8b-instant": "Schnell, günstig, gut für kurze Antworten (Standard).",
    "llama-3.1-70b-versatile": "Größer, bessere Kohärenz & Nuancen, etwas langsamer.",
    "mixtral-8x7b-32768": "Mixture-of-Experts, längerer Kontext, balanced speed.",
}

class GroqClient:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or GROQ_API_KEY
        self.model = model or GROQ_MODEL
        if self.model not in GROQ_MODELS:
            GROQ_MODELS.append(self.model)
        self._client = httpx.Client(timeout=TIMEOUT)

    def available(self) -> bool:
        return bool(self.api_key)

    def set_model(self, model: str) -> bool:
        if model in GROQ_MODELS:
            self.model = model
            return True
        return False

    def list_models(self) -> list[str]:  # pragma: no cover simple access
        return GROQ_MODELS

    def model_hints(self) -> dict[str, str]:  # pragma: no cover
        return {m: MODEL_HINTS.get(m, "(kein Hinweis)") for m in GROQ_MODELS}

    def chat(self, system: str, user: str, max_tokens: int = 280) -> str:
        if not self.api_key:
            raise RuntimeError("GROQ_API_KEY nicht gesetzt.")
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.4,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        last_err: str = ""
        for attempt in range(1, MAX_RETRIES + 2):
            try:
                r = self._client.post(GROQ_BASE_URL, json=payload, headers=headers)
                r.raise_for_status()
                data = r.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "")[:max_tokens]
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    return "[LLM] Auth fehlgeschlagen (401). Prüfe GROQ_API_KEY."
                last_err = f"HTTP {e.response.status_code}: {e.response.text[:100]}"
            except httpx.TimeoutException:
                last_err = "Timeout"
            except Exception as e:  # pragma: no cover
                last_err = f"{type(e).__name__}: {e}"[:140]
            # simple backoff
            if attempt <= MAX_RETRIES:
                continue
        return f"[LLM] Fehlgeschlagen nach {MAX_RETRIES+1} Versuchen: {last_err}"[:200]

    def ping(self) -> str:
        """Kurzer Test ob Key funktioniert."""
        if not self.api_key:
            return "Kein GROQ_API_KEY gesetzt.``setx GROQ_API_KEY '...'."  # guidance
        return self.chat("System: ping", "Sag OK in einem Wort.", max_tokens=5)

    def status(self) -> dict[str, object]:
        return {
            "has_key": bool(self.api_key),
            "active_model": self.model,
            "available_models": self.list_models(),
            "timeout": TIMEOUT,
            "retries": MAX_RETRIES,
        }

_groq_singleton: Optional[GroqClient] = None

def get_groq() -> GroqClient:
    global _groq_singleton
    if _groq_singleton is None:
        _groq_singleton = GroqClient()
    return _groq_singleton
