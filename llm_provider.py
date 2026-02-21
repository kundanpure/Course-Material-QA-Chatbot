"""
LLM Provider Abstraction — switch between Gemini and Groq via env var.

Usage:
    from llm_provider import llm_generate

    text, tokens = await llm_generate("Your prompt here")

Control via .env:
    LLM_PROVIDER=gemini   (default — Google Gemini API)
    LLM_PROVIDER=groq     (Groq cloud — free tier, very fast)
"""

import os
import time
import httpx
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# ─── Config ───────────────────────────────────────────────────────────────────

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower().strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Configure Gemini if key exists
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def get_provider_info() -> dict:
    """Return current LLM provider info for logging."""
    if LLM_PROVIDER == "groq":
        return {"provider": "groq", "model": GROQ_MODEL, "url": "Groq Cloud"}
    return {"provider": "gemini", "model": GEMINI_MODEL, "url": "Google API"}


# ─── Gemini Backend ──────────────────────────────────────────────────────────

async def _gemini_generate(prompt: str) -> tuple:
    """Generate via Google Gemini API. Returns (text, tokens_used)."""
    model = genai.GenerativeModel(model_name=GEMINI_MODEL)
    response = await model.generate_content_async(prompt)

    text = response.text.strip() if response.text else ""
    tokens = getattr(response, "usage_metadata", None)
    token_count = 0
    if tokens:
        token_count = getattr(tokens, "total_token_count", 0) or 0

    return text, token_count


# ─── Groq Backend ────────────────────────────────────────────────────────────

async def _groq_generate(prompt: str) -> tuple:
    """Generate via Groq cloud API (OpenAI-compatible). Returns (text, tokens_used)."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 2048,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    text = data["choices"][0]["message"]["content"].strip()
    tokens = data.get("usage", {}).get("total_tokens", 0)
    return text, tokens


# ─── Unified API ──────────────────────────────────────────────────────────────

async def llm_generate(prompt: str) -> tuple:
    """
    Generate text from the configured LLM provider.
    Returns: (response_text: str, tokens_used: int)

    Switch provider via LLM_PROVIDER env var ("gemini" or "groq").
    """
    if LLM_PROVIDER == "groq":
        return await _groq_generate(prompt)
    else:
        return await _gemini_generate(prompt)
