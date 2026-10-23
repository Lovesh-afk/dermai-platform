"""Chatbot endpoints. Available to any logged-in user; every
conversation is private to the user who created it."""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.user import User
from app.schemas.chat import ChatConversationOut, ChatMessageOut, ChatSendRequest, ChatTurnOut
from app.services.chat import chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


def _conversation_or_404(db: Session, user: User, conversation_id: str):
    try:
        return chat_service.get_conversation(db, user, uuid.UUID(conversation_id))
    except (NotFoundError, ValueError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")


@router.post("/messages", response_model=ChatTurnOut)
def send_message(payload: ChatSendRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv_id = None
    if payload.conversation_id:
        conv_id = _conversation_or_404(db, current_user, payload.conversation_id).id
    conv, user_msg, bot_msg = chat_service.send_message(db, current_user, payload.content.strip(), conv_id)
    return ChatTurnOut(conversation_id=conv.id, user_message=user_msg, assistant_message=bot_msg)


@router.get("/conversations", response_model=list[ChatConversationOut])
def list_conversations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return chat_service.list_conversations(db, current_user)


@router.get("/conversations/{conversation_id}/messages", response_model=list[ChatMessageOut])
def get_messages(conversation_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = _conversation_or_404(db, current_user, conversation_id)
    return chat_service.list_messages(db, conv)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conv = _conversation_or_404(db, current_user, conversation_id)
    chat_service.delete_conversation(db, conv)
