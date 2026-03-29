"""
Progress Routes — Per-user learning progress dashboard
"""
from fastapi import APIRouter, Request
from auth import get_current_user
import db_postgres as db

router = APIRouter(prefix="/api/v1", tags=["Progress"])


@router.get("/progress")
async def get_progress(request: Request):
    """Return per-user learning progress stats.

    Requires authentication. Returns:
    - total_questions, avg_confidence, study_streak, total_study_time_min
    - topics mastery (list with name, question_count, avg_confidence, progress, color)
    - weekly_activity (last 7 days)
    - recommendations (up to 5 AI-style suggestions)
    """
    current = await get_current_user(request)
    user_id = current["user_id"]

    progress = await db.get_user_progress(user_id)

    if not progress:
        # Return empty-state defaults so the frontend always has a shape
        return {
            "total_questions": 0,
            "avg_confidence": 0.0,
            "study_streak": 0,
            "total_study_time_min": 0,
            "documents_uploaded": 0,
            "topics": [],
            "weekly_activity": [],
            "recommendations": [
                {
                    "type": "continue",
                    "message": "Upload a PDF and start asking questions to track your progress!",
                    "priority": "low",
                }
            ],
            "reflection_rate": 0.0,
        }

    return progress
