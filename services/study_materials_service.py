"""
Study Materials Service - Auto-generate flashcards, practice questions, summaries
Innovation: Automatically creates study aids from conversations
"""
from typing import List, Dict, Optional, Any
from datetime import datetime
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from services.llm_router import llm_router
from core.logging import logger
from db.conversation_models import ConversationMessage, ConversationSession


class StudyMaterialsService:
    """
    Generates study materials from conversations
    
    Features:
    - Auto-generate flashcards from Q&A
    - Create practice questions
    - Generate summaries
    - Export to PDF/Anki format
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def generate_flashcards_from_conversation(
        self,
        session_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        Generate flashcards from conversation history
        
        Returns list of {question, answer, source} dicts
        """
        
        # Get conversation messages
        query = select(ConversationMessage).where(
            ConversationMessage.session_id == session_id
        ).order_by(ConversationMessage.created_at)
        
        if limit:
            query = query.limit(limit * 2)  # Q&A pairs
        
        result = await self.session.execute(query)
        messages = result.scalars().all()
        
        flashcards = []
        
        # Create flashcards from user questions and assistant answers
        for i in range(0, len(messages) - 1, 2):
            if messages[i].role == "user" and messages[i+1].role == "assistant":
                flashcard = {
                    "question": messages[i].content,
                    "answer": messages[i+1].content,
                    "source": f"Conversation {session_id}",
                    "created_at": messages[i].created_at.isoformat(),
                    "confidence": messages[i+1].confidence or 0.0
                }
                flashcards.append(flashcard)
        
        logger.info(f"Generated {len(flashcards)} flashcards from session {session_id}")
        return flashcards
    
    async def generate_practice_questions(
        self,
        content: str,
        num_questions: int = 5,
        difficulty: str = "medium"
    ) -> List[Dict[str, Any]]:
        """
        Generate practice questions from content using LLM
        
        Returns list of {question, options, correct_answer, explanation}
        """
        
        prompt = f"""Generate {num_questions} multiple-choice practice questions based on this content.
Difficulty level: {difficulty}

Content:
{content[:2000]}

Format each question as JSON:
{{
    "question": "...",
    "options": ["A) ...", "B) ...", "C) ...", "D) ..."],
    "correct_answer": "A",
    "explanation": "..."
}}

Generate exactly {num_questions} questions in a JSON array."""
        
        try:
            response = await llm_router.chat(
                messages=[
                    {"role": "system", "content": "You are an expert at creating educational practice questions."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            # Parse JSON response (simplified - in production, use proper JSON parsing)
            import json
            questions = json.loads(response["content"])
            
            logger.info(f"Generated {len(questions)} practice questions")
            return questions
            
        except Exception as e:
            logger.error(f"Failed to generate practice questions: {e}")
            return []
    
    async def generate_summary(
        self,
        session_id: str,
        summary_type: str = "concise"
    ) -> Dict[str, str]:
        """
        Generate summary of conversation
        
        summary_type: 'concise', 'detailed', 'bullet_points'
        """
        
        # Get all messages
        result = await self.session.execute(
            select(ConversationMessage).where(
                ConversationMessage.session_id == session_id
            ).order_by(ConversationMessage.created_at)
        )
        messages = result.scalars().all()
        
        # Build conversation text
        conversation_text = "\n".join([
            f"{msg.role.upper()}: {msg.content}"
            for msg in messages
        ])
        
        # Generate summary using LLM
        prompts = {
            "concise": "Provide a concise 2-3 sentence summary of this conversation:",
            "detailed": "Provide a detailed summary covering all main points discussed:",
            "bullet_points": "Summarize the key points from this conversation as bullet points:"
        }
        
        try:
            response = await llm_router.chat(
                messages=[
                    {"role": "system", "content": "You are an expert at summarizing educational conversations."},
                    {"role": "user", "content": f"{prompts.get(summary_type, prompts['concise'])}\n\n{conversation_text[:3000]}"}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            return {
                "summary": response["content"],
                "type": summary_type,
                "message_count": len(messages),
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            return {"summary": "", "error": str(e)}
    
    async def export_to_anki(
        self,
        flashcards: List[Dict[str, str]],
        deck_name: str = "My Deck"
    ) -> str:
        """
        Export flashcards to Anki format (CSV)
        
        Returns CSV string that can be imported into Anki
        """
        
        csv_lines = ["#separator:tab", "#html:true", "#deck:" + deck_name, ""]
        
        for card in flashcards:
            question = card["question"].replace("\n", "<br>").replace("\t", " ")
            answer = card["answer"].replace("\n", "<br>").replace("\t", " ")
            csv_lines.append(f"{question}\t{answer}")
        
        return "\n".join(csv_lines)
    
    async def export_to_pdf(
        self,
        flashcards: List[Dict[str, str]],
        title: str = "Study Materials"
    ) -> bytes:
        """
        Export flashcards to PDF
        
        Returns PDF binary data
        """
        
        # Simplified PDF generation - in production, use reportlab or similar
        from io import BytesIO
        
        # For now, return formatted text (upgrade to proper PDF later)
        pdf_content = f"# {title}\n\n"
        
        for i, card in enumerate(flashcards, 1):
            pdf_content += f"## Card {i}\n\n"
            pdf_content += f"**Q:** {card['question']}\n\n"
            pdf_content += f"**A:** {card['answer']}\n\n"
            pdf_content += "---\n\n"
        
        return pdf_content.encode('utf-8')
    
    async def generate_concept_map(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Generate concept map from conversation
        
        Returns nodes and edges for visualization
        """
        
        result = await self.session.execute(
            select(ConversationMessage).where(
                ConversationMessage.session_id == session_id
            )
        )
        messages = result.scalars().all()
        
        # Extract concepts using LLM
        conversation_text = "\n".join([msg.content for msg in messages if msg.role == "assistant"])
        
        try:
            response = await llm_router.chat(
                messages=[
                    {"role": "system", "content": "Extract key concepts and their relationships from this text. Return as JSON with 'nodes' and 'edges' arrays."},
                    {"role": "user", "content": f"Extract concepts:\n\n{conversation_text[:2000]}"}
                ],
                temperature=0.5,
                max_tokens=1000
            )
            
            import json
            concept_map = json.loads(response["content"])
            
            return concept_map
            
        except Exception as e:
            logger.error(f"Failed to generate concept map: {e}")
            return {"nodes": [], "edges": []}


# Dependency injection
async def get_study_materials_service(session: AsyncSession) -> StudyMaterialsService:
    return StudyMaterialsService(session)
