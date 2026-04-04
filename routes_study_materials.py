"""
Study Materials Routes — Topic-based AI learning hub.
User enters a topic → AI generates study materials (guide, flashcards, quiz, concepts, resources).
Optionally enhanced with uploaded PDF content.
"""
import json
import re
import time
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

import db_postgres as db
from auth import get_current_user
from llm_provider import llm_generate

router = APIRouter(prefix="/api/v1/study-materials", tags=["Study Materials"])


# ─── Request / Response Models ─────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    topic: str
    tool: str  # "guide" | "flashcards" | "quiz" | "concepts" | "resources"
    doc_id: Optional[str] = None  # optional PDF context


# ─── Prompt Templates ─────────────────────────────────────────────────────────

def _build_prompt(topic: str, tool: str, doc_context: str = "") -> str:
    """Build specialized LLM prompt for each tool type."""

    context_block = ""
    if doc_context:
        context_block = f"""
You also have access to uploaded document content. Use this to make your response more specific and grounded:

--- DOCUMENT CONTENT ---
{doc_context}
--- END DOCUMENT ---
"""

    prompts = {
        "guide": f"""You are an expert tutor. Create a comprehensive study guide on: "{topic}"
{context_block}
Return a well-structured markdown study guide with these sections:

## 📋 Overview
Brief introduction to the topic (2-3 sentences).

## 🎯 Prerequisites
What should the student already know before studying this topic.

## 📚 Key Concepts
Detailed explanations of the most important concepts (5-8 concepts with clear explanations).

## 📐 Important Formulas & Definitions
Any key formulas, theorems, or definitions. Use LaTeX notation where appropriate.

## 🗂️ Learning Path
Recommended order to study subtopics, from foundational to advanced.

## ⚡ Quick Revision Points
8-10 bullet points summarizing the most exam-critical information.

Make it educational, clear, and thorough. Use examples where helpful.""",

        "flashcards": f"""You are an expert tutor creating study flashcards on: "{topic}"
{context_block}
Generate exactly 12 flashcards covering the most important concepts.

Return ONLY a valid JSON array (no markdown fences), where each item has:
- "question": a clear, specific question
- "answer": a concise but complete answer (2-4 sentences max)
- "difficulty": "easy", "medium", or "hard"

Example format:
[
  {{"question": "What is X?", "answer": "X is...", "difficulty": "easy"}},
  {{"question": "Explain Y", "answer": "Y works by...", "difficulty": "medium"}}
]

Cover a mix of definitions, concepts, applications, and comparisons. Make questions exam-style.""",

        "quiz": f"""You are an expert tutor creating a practice quiz on: "{topic}"
{context_block}
Generate exactly 10 quiz questions — 7 multiple choice (MCQ) and 3 short answer.

Return ONLY a valid JSON array (no markdown fences), where each item has:
- "id": sequential number (1-10)
- "type": "mcq" or "short_answer"
- "question": clear question text
- "options": array of 4 options (for MCQ only, null for short_answer)
- "correct_answer": the correct option letter "A"/"B"/"C"/"D" for MCQ, or a short text for short_answer
- "explanation": why this is the correct answer (1-2 sentences)
- "difficulty": "easy", "medium", or "hard"

Example:
[
  {{"id": 1, "type": "mcq", "question": "What is...?", "options": ["A) ...", "B) ...", "C) ...", "D) ..."], "correct_answer": "B", "explanation": "Because...", "difficulty": "medium"}},
  {{"id": 2, "type": "short_answer", "question": "Explain...", "options": null, "correct_answer": "It is...", "explanation": "This is important because...", "difficulty": "hard"}}
]

Make questions progressively harder. Cover breadth of the topic.""",

        "concepts": f"""You are an expert tutor creating a concept map for: "{topic}"
{context_block}
Create a hierarchical concept map showing how subtopics relate to each other.

Return ONLY a valid JSON object (no markdown fences) with this structure:
{{
  "root": "{topic}",
  "children": [
    {{
      "name": "Subtopic 1",
      "description": "Brief description",
      "children": [
        {{"name": "Sub-subtopic A", "description": "Brief desc", "children": []}},
        {{"name": "Sub-subtopic B", "description": "Brief desc", "children": []}}
      ]
    }},
    {{
      "name": "Subtopic 2",
      "description": "Brief description",
      "children": [
        {{"name": "Sub-subtopic C", "description": "Brief desc", "children": []}}
      ]
    }}
  ]
}}

Include 4-6 main subtopics, each with 2-4 sub-subtopics. Keep descriptions under 15 words.""",

        "resources": f"""You are an expert tutor recommending learning resources for: "{topic}"
{context_block}
Recommend the best learning resources across different formats.

Return ONLY a valid JSON array (no markdown fences):
[
  {{"title": "Resource Name", "type": "video", "url": "https://...", "description": "Why this is useful", "level": "beginner"}},
  {{"title": "Resource Name", "type": "course", "url": "https://...", "description": "Why this is useful", "level": "intermediate"}}
]

Include exactly 10 resources with this mix:
- 3 YouTube videos/channels (use real, well-known ones)
- 2 online courses (Coursera, edX, Khan Academy, etc.)
- 2 documentation/tutorials (official docs, MDN, GeeksForGeeks, etc.)
- 2 books (with real book titles and authors)
- 1 interactive tool (visualizations, playgrounds, etc.)

"type" must be one of: "video", "course", "documentation", "book", "interactive"
"level" must be one of: "beginner", "intermediate", "advanced"
Use REAL, well-known resources that actually exist. Prefer free resources.""",
    }

    return prompts.get(tool, prompts["guide"])


def _strip_json_fences(text: str) -> str:
    """Strip markdown code fences that LLMs wrap around JSON."""
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*\n?', '', text)
    text = re.sub(r'\n?```\s*$', '', text)
    return text.strip()


# ─── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/topics")
async def get_topic_suggestions(request: Request):
    """Get dynamic topic suggestions based on user's activity."""
    current = await get_current_user(request)
    topics = await db.get_user_topics(current["user_id"])

    # Always include some popular fallback topics
    fallbacks = [
        {"name": "Data Structures & Algorithms", "source": "popular", "count": 0},
        {"name": "Machine Learning", "source": "popular", "count": 0},
        {"name": "Operating Systems", "source": "popular", "count": 0},
        {"name": "Database Management", "source": "popular", "count": 0},
        {"name": "Computer Networks", "source": "popular", "count": 0},
        {"name": "Object Oriented Programming", "source": "popular", "count": 0},
    ]

    seen = {t["name"].lower() for t in topics}
    for fb in fallbacks:
        if fb["name"].lower() not in seen and len(topics) < 12:
            topics.append(fb)

    return {"topics": topics}


@router.post("/generate")
async def generate_study_material(req: GenerateRequest, request: Request):
    """Generate AI study material for a topic.

    tool: "guide" | "flashcards" | "quiz" | "concepts" | "resources"
    doc_id: optional — if provided, uses uploaded PDF content as context
    """
    await get_current_user(request)  # require auth

    if not req.topic.strip():
        raise HTTPException(400, "Topic is required")

    valid_tools = {"guide", "flashcards", "quiz", "concepts", "resources"}
    if req.tool not in valid_tools:
        raise HTTPException(400, f"Invalid tool. Must be one of: {valid_tools}")

    # Optional: pull document chunks for context
    doc_context = ""
    if req.doc_id:
        try:
            # Import the in-memory document store from main app
            from production_agentic import documents_store, chunk_lookup
            if req.doc_id in documents_store:
                doc_data = documents_store[req.doc_id]
                chunks = chunk_lookup.get(req.doc_id, doc_data.get("chunks", []))
                # Build compact context (cap at ~4000 chars)
                page_texts = []
                seen_pages = set()
                for c in sorted(chunks, key=lambda x: x.get("page_num", 0)):
                    pk = c.get("page_num", 0)
                    if pk in seen_pages:
                        continue
                    seen_pages.add(pk)
                    page_texts.append(f"[Page {pk}] {c['text'][:600]}")
                    if sum(len(t) for t in page_texts) > 4000:
                        break
                doc_context = "\n\n".join(page_texts)
        except ImportError:
            pass  # if import fails, proceed without doc context

    prompt = _build_prompt(req.topic, req.tool, doc_context)

    start = time.time()
    try:
        raw_text, tokens = await llm_generate(prompt)
    except Exception as e:
        print(f"[STUDY MATERIALS] LLM error: {e}")
        raise HTTPException(500, "Failed to generate study material. Please try again.")

    gen_time_ms = (time.time() - start) * 1000
    print(f"[STUDY MATERIALS] Generated {req.tool} for '{req.topic}' in {gen_time_ms:.0f}ms ({tokens} tokens)")

    # Parse response based on tool type
    if req.tool == "guide":
        # Guide returns markdown — pass through as-is
        return {
            "tool": "guide",
            "topic": req.topic,
            "content": raw_text,
            "generation_time_ms": round(gen_time_ms),
            "tokens_used": tokens,
        }
    else:
        # Other tools return JSON — parse it
        try:
            cleaned = _strip_json_fences(raw_text)
            parsed = json.loads(cleaned)
            return {
                "tool": req.tool,
                "topic": req.topic,
                "content": parsed,
                "generation_time_ms": round(gen_time_ms),
                "tokens_used": tokens,
            }
        except json.JSONDecodeError as e:
            print(f"[STUDY MATERIALS] JSON parse error: {e}")
            print(f"[STUDY MATERIALS] Raw: {raw_text[:500]}")
            # Fallback: try to extract JSON from the response
            json_match = re.search(r'[\[\{].*[\]\}]', raw_text, re.DOTALL)
            if json_match:
                try:
                    parsed = json.loads(json_match.group())
                    return {
                        "tool": req.tool,
                        "topic": req.topic,
                        "content": parsed,
                        "generation_time_ms": round(gen_time_ms),
                        "tokens_used": tokens,
                    }
                except json.JSONDecodeError:
                    pass
            raise HTTPException(500, "AI returned invalid format. Please try again.")
