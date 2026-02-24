"""
LLM Provider for Evaluation — separate API keys to isolate token usage from the RAG pipeline.

Usage:
    from llm_eval_provider import eval_llm_generate

    text, tokens = await eval_llm_generate("Your prompt here")

Control via .env:
    EVAL_LLM_PROVIDER=gemini      (default — Google Gemini API)
    EVAL_LLM_PROVIDER=groq        (Groq cloud — free tier, very fast)

    EVAL_GEMINI_API_KEY=AIza...    (separate Gemini key for evaluation)
    EVAL_GROQ_API_KEY=gsk_...      (separate Groq key for evaluation)

Falls back to main keys (GEMINI_API_KEY / GROQ_API_KEY) if eval-specific keys aren't set.
"""

import os
import httpx
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# ─── Config ───────────────────────────────────────────────────────────────────

EVAL_LLM_PROVIDER = os.getenv("EVAL_LLM_PROVIDER", os.getenv("LLM_PROVIDER", "gemini")).lower().strip()
EVAL_GEMINI_MODEL  = os.getenv("EVAL_GEMINI_MODEL", os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp"))
EVAL_GEMINI_API_KEY = os.getenv("EVAL_GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
EVAL_GROQ_API_KEY   = os.getenv("EVAL_GROQ_API_KEY", os.getenv("GROQ_API_KEY", ""))
EVAL_GROQ_MODEL     = os.getenv("EVAL_GROQ_MODEL", os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))

# Configure Gemini for evaluation if key exists
if EVAL_GEMINI_API_KEY and EVAL_LLM_PROVIDER == "gemini":
    genai.configure(api_key=EVAL_GEMINI_API_KEY)


def get_eval_provider_info() -> dict:
    """Return current eval LLM provider info for logging."""
    if EVAL_LLM_PROVIDER == "groq":
        return {"provider": "groq", "model": EVAL_GROQ_MODEL, "purpose": "evaluation"}
    return {"provider": "gemini", "model": EVAL_GEMINI_MODEL, "purpose": "evaluation"}


# ─── Gemini Backend ──────────────────────────────────────────────────────────

async def _eval_gemini_generate(prompt: str) -> tuple:
    """Generate via Google Gemini API (eval keys). Returns (text, tokens_used)."""
    model = genai.GenerativeModel(model_name=EVAL_GEMINI_MODEL)
    response = await model.generate_content_async(prompt)

    text = response.text.strip() if response.text else ""
    tokens = getattr(response, "usage_metadata", None)
    token_count = 0
    if tokens:
        token_count = getattr(tokens, "total_token_count", 0) or 0

    return text, token_count


# ─── Groq Backend ────────────────────────────────────────────────────────────

async def _eval_groq_generate(prompt: str) -> tuple:
    """Generate via Groq cloud API (eval keys). Returns (text, tokens_used)."""
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {EVAL_GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": EVAL_GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.4,
        "max_tokens": 2048,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    text = data["choices"][0]["message"]["content"].strip()
    tokens = data.get("usage", {}).get("total_tokens", 0)
    return text, tokens


# ─── Unified Eval API ────────────────────────────────────────────────────────

async def eval_llm_generate(prompt: str) -> tuple:
    """
    Generate text using the evaluation-dedicated LLM provider.
    Returns: (response_text: str, tokens_used: int)

    Uses separate API keys from the RAG pipeline to keep token budgets isolated.
    Switch provider via EVAL_LLM_PROVIDER env var ("gemini" or "groq").
    """
    if EVAL_LLM_PROVIDER == "groq":
        return await _eval_groq_generate(prompt)
    else:
        return await _eval_gemini_generate(prompt)
