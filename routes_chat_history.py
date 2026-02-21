"""
Chat History Routes — CRUD for chat sessions and messages
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

import db_postgres as db
from auth import get_current_user

router = APIRouter(prefix="/api/v1/chat", tags=["Chat History"])


# ─── Request Models ────────────────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    title: Optional[str] = "New Chat"


class UpdateTitleRequest(BaseModel):
    title: str


# ─── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions(request: Request, limit: int = 50):
    """List all chat sessions for the authenticated user."""
    current = await get_current_user(request)
    sessions = await db.get_user_sessions(current["user_id"], limit=limit)
    # Convert datetime objects to strings for JSON
    for s in sessions:
        s["created_at"] = str(s["created_at"])
        s["updated_at"] = str(s["updated_at"])
    return {"sessions": sessions}


@router.post("/sessions")
async def create_session(request: Request, req: CreateSessionRequest):
    """Create a new chat session."""
    current = await get_current_user(request)
    session = await db.create_chat_session(current["user_id"], req.title or "New Chat")
    if not session:
        raise HTTPException(500, "Failed to create session")
    session["created_at"] = str(session["created_at"])
    session["updated_at"] = str(session["updated_at"])
    return session


@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: int, request: Request):
    """Get all messages for a specific chat session."""
    current = await get_current_user(request)
    messages = await db.get_session_messages(session_id, current["user_id"])
    for m in messages:
        m["created_at"] = str(m["created_at"])
    return {"messages": messages}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: int, request: Request):
    """Delete a chat session and all its messages."""
    current = await get_current_user(request)
    deleted = await db.delete_chat_session(session_id, current["user_id"])
    if not deleted:
        raise HTTPException(404, "Session not found or not owned by you")
    return {"status": "deleted"}


@router.patch("/sessions/{session_id}")
async def update_title(session_id: int, request: Request, req: UpdateTitleRequest):
    """Update a session's title."""
    current = await get_current_user(request)
    updated = await db.update_session_title(session_id, current["user_id"], req.title)
    if not updated:
        raise HTTPException(404, "Session not found or not owned by you")
    return {"status": "updated"}
