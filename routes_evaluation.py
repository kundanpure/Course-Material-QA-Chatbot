"""
Evaluation Routes — AI-powered exam answer grading with separate LLM keys.
"""

import json
import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

from llm_eval_provider import eval_llm_generate, get_eval_provider_info

router = APIRouter(prefix="/api/v1", tags=["Evaluation"])


# ─── Request / Response Models ─────────────────────────────────────────────────

class EvaluationRequest(BaseModel):
    question: str
    student_answer: str
    grading_mode: str = "moderate"  # "lenient" | "moderate" | "strict"


class EvaluationResponse(BaseModel):
    score: float
    strengths: List[str]
    missing_concepts: List[str]
    improvements: List[str]
    model_answer: str
    grading_mode: str


# ─── Grading Prompt Builder ────────────────────────────────────────────────────

def build_grading_prompt(question: str, student_answer: str, mode: str) -> str:
    tone_instruction = {
        "lenient": "Be supportive and slightly forgiving. Reward partial understanding.",
        "moderate": "Grade like a normal university professor. Be fair and balanced.",
        "strict": "Grade very strictly. Penalize missing depth, incomplete explanations, and lack of precision."
    }.get(mode.lower(), "Grade like a normal university professor.")

    return f"""
You are a university professor evaluating an exam answer.

Grading style: {tone_instruction}

Question:
{question}

Student Answer:
{student_answer}

Evaluate based on:
1. Concept correctness
2. Completeness
3. Depth of explanation
4. Clarity

Return ONLY valid JSON in this exact format:

{{
  "score": number between 0 and 10,
  "strengths": ["point1", "point2"],
  "missing_concepts": ["point1", "point2"],
  "improvements": ["point1", "point2"],
  "model_answer": "ideal full-mark answer"
}}
"""


def _strip_markdown_fences(text: str) -> str:
    """Strip markdown code fences (```json ... ```) that LLMs often wrap around JSON."""
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*\n?', '', text)
    text = re.sub(r'\n?```\s*$', '', text)
    return text.strip()


# ─── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_answer(request: EvaluationRequest):
    """Evaluate a student's exam answer using AI grading."""
    try:
        provider = get_eval_provider_info()
        print(f"[EVALUATION] Using {provider['provider']} ({provider['model']}) for grading")

        prompt = build_grading_prompt(
            request.question,
            request.student_answer,
            request.grading_mode
        )

        response_text, tokens = await eval_llm_generate(prompt)
        print(f"[EVALUATION] LLM returned {tokens} tokens")

        # Strip markdown fences before parsing
        cleaned = _strip_markdown_fences(response_text)
        data = json.loads(cleaned)

        return EvaluationResponse(
            score=float(data.get("score", 0)),
            strengths=data.get("strengths", []),
            missing_concepts=data.get("missing_concepts", []),
            improvements=data.get("improvements", []),
            model_answer=data.get("model_answer", ""),
            grading_mode=request.grading_mode
        )

    except json.JSONDecodeError as e:
        print(f"[EVALUATION ERROR] Failed to parse LLM JSON: {e}")
        print(f"[EVALUATION ERROR] Raw response: {response_text[:500]}")
        raise HTTPException(status_code=500, detail="Evaluation failed — LLM returned invalid JSON")
    except Exception as e:
        print(f"[EVALUATION ERROR] {e}")
        raise HTTPException(status_code=500, detail="Evaluation failed")
