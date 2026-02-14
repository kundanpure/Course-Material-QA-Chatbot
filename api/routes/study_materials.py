"""
Study Materials API Routes
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from services.study_materials_service import StudyMaterialsService
from api.deps import get_current_user
from core.logging import logger

router = APIRouter()


# Request/Response Models
class FlashcardResponse(BaseModel):
    question: str
    answer: str
    source: str
    confidence: float


class GeneratePracticeQuestionsRequest(BaseModel):
    content: str
    num_questions: int = 5
    difficulty: str = "medium"


class ExportRequest(BaseModel):
    session_id: str
    format: str  # 'anki' or 'pdf'
    deck_name: Optional[str] = "My Study Deck"


@router.get("/flashcards/{session_id}", response_model=List[FlashcardResponse])
async def get_flashcards(
    session_id: str,
    limit: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Generate flashcards from conversation session
    """
    service = StudyMaterialsService(db)
    
    flashcards = await service.generate_flashcards_from_conversation(
        session_id=session_id,
        limit=limit
    )
    
    return flashcards


@router.post("/practice-questions")
async def generate_practice_questions(
    request: GeneratePracticeQuestionsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Generate practice questions from content
    """
    service = StudyMaterialsService(db)
    
    questions = await service.generate_practice_questions(
        content=request.content,
        num_questions=request.num_questions,
        difficulty=request.difficulty
    )
    
    return {"questions": questions}


@router.get("/summary/{session_id}")
async def get_conversation_summary(
    session_id: str,
    summary_type: str = "concise",
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Generate summary of conversation
    
    summary_type: 'concise', 'detailed', 'bullet_points'
    """
    service = StudyMaterialsService(db)
    
    summary = await service.generate_summary(
        session_id=session_id,
        summary_type=summary_type
    )
    
    return summary


@router.post("/export")
async def export_study_materials(
    request: ExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Export study materials to Anki or PDF format
    """
    service = StudyMaterialsService(db)
    
    # Get flashcards
    flashcards = await service.generate_flashcards_from_conversation(
        session_id=request.session_id
    )
    
    if request.format == "anki":
        csv_content = await service.export_to_anki(
            flashcards=flashcards,
            deck_name=request.deck_name
        )
        return {
            "format": "anki",
            "content": csv_content,
            "filename": f"{request.deck_name}.txt"
        }
    
    elif request.format == "pdf":
        pdf_content = await service.export_to_pdf(
            flashcards=flashcards,
            title=request.deck_name
        )
        return {
            "format": "pdf",
            "content": pdf_content.decode('utf-8'),
            "filename": f"{request.deck_name}.pdf"
        }
    
    else:
        raise HTTPException(status_code=400, detail="Invalid format. Use 'anki' or 'pdf'")


@router.get("/concept-map/{session_id}")
async def get_concept_map(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Generate concept map visualization data from conversation
    """
    service = StudyMaterialsService(db)
    
    concept_map = await service.generate_concept_map(session_id=session_id)
    
    return concept_map
