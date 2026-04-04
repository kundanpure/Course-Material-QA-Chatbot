"""
Evaluation Routes — AI-powered exam answer grading with separate LLM keys.
Supports:
  - POST /api/v1/extract-text   → extract text from uploaded PDF/DOCX
  - POST /api/v1/evaluate       → grade answer (JSON or multipart with reference file)
"""

import io
import json
import re
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional

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


# ─── Text Extraction Helper ────────────────────────────────────────────────────

def _extract_text_from_bytes(filename: str, data: bytes) -> str:
    """Extract plain text from PDF or DOCX bytes."""
    filename_lower = filename.lower()

    if filename_lower.endswith(".pdf"):
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                return "\n".join(
                    page.extract_text() or "" for page in pdf.pages
                ).strip()
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="pdfplumber not installed. Run: pip install pdfplumber"
            )

    elif filename_lower.endswith((".docx", ".doc")):
        try:
            import docx
            doc = docx.Document(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip()).strip()
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="python-docx not installed. Run: pip install python-docx"
            )

    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Only PDF and DOCX are supported."
        )


# ─── /extract-text Endpoint ───────────────────────────────────────────────────

@router.post("/extract-text")
async def extract_text(file: UploadFile = File(...)):
    """Extract plain text from an uploaded PDF or DOCX file."""
    data = await file.read()
    try:
        text = _extract_text_from_bytes(file.filename or "", data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Text extraction failed: {e}")

    return JSONResponse({"text": text, "filename": file.filename})


# ─── Grading Prompt Builder ────────────────────────────────────────────────────

def build_grading_prompt(
    question: str,
    student_answer: str,
    mode: str,
    reference_text: Optional[str] = None,
) -> str:
    tone_instruction = {
        "lenient": "Be supportive and slightly forgiving. Reward partial understanding.",
        "moderate": "Grade like a normal university professor. Be fair and balanced.",
        "strict": "Grade very strictly. Penalize missing depth, incomplete explanations, and lack of precision.",
    }.get(mode.lower(), "Grade like a normal university professor.")

    reference_section = ""
    if reference_text:
        reference_section = f"""
Reference Material (use this as the authoritative source for grading):
{reference_text}
"""

    return f"""You are a university professor evaluating an exam answer. You MUST respond with ONLY a valid JSON object. No explanations before or after. No markdown fences. Just pure JSON.

Grading style: {tone_instruction}

=== QUESTION (evaluate the student based on this question) ===
{question}
{reference_section}
=== STUDENT ANSWER (this is what the student wrote) ===
{student_answer}
=== END OF INPUT ===

Evaluate the student answer against the question based on:
1. Concept correctness
2. Completeness
3. Depth of explanation
4. Clarity

IMPORTANT: The question and answer text above may have been extracted from PDF files and may contain formatting artifacts. Treat them as-is and do your best evaluation.

You MUST respond with ONLY this exact JSON structure and nothing else:

{{"score": 7.5, "strengths": ["point1", "point2"], "missing_concepts": ["point1", "point2"], "improvements": ["point1", "point2"], "model_answer": "The ideal full-mark answer goes here"}}"""


def _strip_markdown_fences(text: str) -> str:
    """Strip markdown code fences (```json ... ```) that LLMs often wrap around JSON."""
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*\n?', '', text)
    text = re.sub(r'\n?```\s*$', '', text)
    return text.strip()


# ─── /evaluate Endpoint (JSON — no reference file) ────────────────────────────

@router.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_answer(request: EvaluationRequest):
    """Evaluate a student's exam answer using AI grading (plain JSON, no file)."""
    return await _run_evaluation(
        question=request.question,
        student_answer=request.student_answer,
        grading_mode=request.grading_mode,
        reference_text=None,
    )


# ─── /evaluate/with-reference Endpoint (multipart — includes reference file) ──

@router.post("/evaluate/with-reference", response_model=EvaluationResponse)
async def evaluate_answer_with_reference(
    question: str = Form(...),
    student_answer: str = Form(...),
    grading_mode: str = Form("moderate"),
    reference_file: UploadFile = File(...),
):
    """Evaluate a student's answer with an optional reference material file."""
    data = await reference_file.read()
    try:
        reference_text = _extract_text_from_bytes(reference_file.filename or "", data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read reference file: {e}")

    return await _run_evaluation(
        question=question,
        student_answer=student_answer,
        grading_mode=grading_mode,
        reference_text=reference_text,
    )


# ─── Shared Evaluation Logic ───────────────────────────────────────────────────

async def _run_evaluation(
    question: str,
    student_answer: str,
    grading_mode: str,
    reference_text: Optional[str],
) -> EvaluationResponse:
    response_text = ""
    try:
        provider = get_eval_provider_info()
        print(f"[EVALUATION] Using {provider['provider']} ({provider['model']}) for grading")

        prompt = build_grading_prompt(question, student_answer, grading_mode, reference_text)
        response_text, tokens = await eval_llm_generate(prompt)
        print(f"[EVALUATION] LLM returned {tokens} tokens")

        cleaned = _strip_markdown_fences(response_text)
        data = json.loads(cleaned)

        return EvaluationResponse(
            score=float(data.get("score", 0)),
            strengths=data.get("strengths", []),
            missing_concepts=data.get("missing_concepts", []),
            improvements=data.get("improvements", []),
            model_answer=data.get("model_answer", ""),
            grading_mode=grading_mode,
        )

    except json.JSONDecodeError as e:
        print(f"[EVALUATION ERROR] Failed to parse LLM JSON: {e}")
        print(f"[EVALUATION ERROR] Raw response: {response_text[:500]}")
        raise HTTPException(
            status_code=500,
            detail="Evaluation failed — LLM returned invalid JSON"
        )
    except Exception as e:
        print(f"[EVALUATION ERROR] {e}")
        raise HTTPException(status_code=500, detail="Evaluation failed")
