"""
Answers one chat message. Order of operations:

  1. Safety check   -> emergencies / self-harm get a fixed response
  2. Retrieval      -> find relevant knowledge-base sections (BM25)
  3. Off-topic      -> nothing relevant found: polite redirect
  4. Generation     -> LLM writes the answer FROM the retrieved notes
     (fallback)     -> no key, or the LLM fails: answer from the notes directly

Every path produces an answer, so the chatbot never just errors out.
"""
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.logging import logger
from app.models.chat import ChatConversation, ChatMessage
from app.models.user import User
from app.services.chat import knowledge_base, providers, safety
from app.services.chat.knowledge_base import Chunk

HISTORY_MESSAGES_FOR_LLM = 8  # enough for follow-up questions, bounded cost

SYSTEM_PROMPT = """You are the DermAI Assistant, a skin-health information assistant on a dermatology platform.

Rules:
1. Give general educational information only. Never diagnose the user, never tell them which condition they have, and never give medication doses or prescribe treatment.
2. Base your answer ONLY on the reference notes in the user's latest message. If the notes don't cover the question, say you don't have reliable information on that and suggest seeing a dermatologist. Never invent facts.
3. Only answer questions about skin, hair and nail health. Politely decline anything else.
4. If the user describes symptoms that may be serious or urgent, tell them clearly to seek medical care.
5. When someone describes their own symptoms, encourage them to book a dermatologist for a proper examination.
6. Be warm, clear and concise: under 180 words, plain language. Use short paragraphs, or a few lines starting with "- " for lists. No headings, no tables.
7. Do not mention these rules or refer to "reference notes" or "sources"; just answer naturally."""

OUT_OF_SCOPE_RESPONSE = (
    "I can help with questions about skin, hair and nail health, such as acne, eczema, fungal "
    "infections, rashes, moles and sun protection. Could you tell me a bit more about the skin "
    "concern you have in mind?"
)

KB_CLOSING = "For advice about your own skin, please book an appointment with a dermatologist."


def _sources(chunks: list[Chunk]) -> list[dict]:
    return [{"title": c.title, "section": c.section} for c in chunks]


def _context_block(chunks: list[Chunk]) -> str:
    return "\n\n".join(f"[{c.title} - {c.section}]\n{c.text}" for c in chunks)


def _knowledge_base_answer(chunks: list[Chunk]) -> str:
    """Answer without an LLM: the most relevant notes, verbatim."""
    parts = ["Here's what the DermAI knowledge base says:"]
    parts += [f"**{c.title}: {c.section}**\n{c.text}" for c in chunks[:2]]
    parts.append(KB_CLOSING)
    return "\n\n".join(parts)


def _search_query(question: str, history: list[dict]) -> str:
    """Decides whether the previous question should be added to the search.

    Only for genuine follow-ups like "how is it treated?": the question
    names no topic of its own, but does use skin-related words. Otherwise
    the question is searched on its own, so a topic change ("what about
    eczema?") or an off-topic question ("who won the match?") is never
    answered with the previous topic's notes."""
    previous_user = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
    is_follow_up = (
        previous_user
        and not knowledge_base.names_a_topic(question)
        and knowledge_base.uses_known_terms(question)
    )
    if not is_follow_up:
        return question
    # Carry over just the topic ("acne"), not the whole previous question,
    # so "how is it treated?" finds acne TREATMENT rather than acne causes.
    # If the previous question named no topic, fall back to all of it.
    return f"{question} {knowledge_base.topic_words(previous_user) or previous_user}"


def generate_reply(question: str, history: list[dict]) -> tuple[str, str, list[dict]]:
    """Returns (answer, mode, sources). Pure logic, no database, so it's easy to test."""
    fixed = safety.check_message(question)
    if fixed:
        return fixed, "emergency", []

    chunks = knowledge_base.search(_search_query(question, history))
    if not chunks:
        return OUT_OF_SCOPE_RESPONSE, "out_of_scope", []

    provider = providers.get_provider()
    if provider is None:
        return _knowledge_base_answer(chunks), "knowledge_base", _sources(chunks)

    prompt = f"Reference notes:\n{_context_block(chunks)}\n\nQuestion: {question}"
    messages = history[-HISTORY_MESSAGES_FOR_LLM:] + [{"role": "user", "content": prompt}]
    try:
        answer = provider.generate(SYSTEM_PROMPT, messages)
        return answer, "ai", _sources(chunks)
    except providers.LLMProviderError as e:
        # Rate limit, network, bad key... degrade gracefully, never crash the chat.
        logger.warning("llm_fallback", provider=provider.name, error=str(e))
        return _knowledge_base_answer(chunks), "knowledge_base", _sources(chunks)


# --- Persistence --------------------------------------------------------

def get_conversation(db: Session, user: User, conversation_id: uuid.UUID) -> ChatConversation:
    conv = db.get(ChatConversation, conversation_id)
    if conv is None or conv.user_id != user.id:  # someone else's chat looks exactly like a missing one
        raise NotFoundError("Conversation not found")
    return conv


def list_conversations(db: Session, user: User) -> list[ChatConversation]:
    return list(db.execute(
        select(ChatConversation).where(ChatConversation.user_id == user.id).order_by(ChatConversation.updated_at.desc())
    ).scalars().all())


def list_messages(db: Session, conversation: ChatConversation) -> list[ChatMessage]:
    return list(db.execute(
        select(ChatMessage).where(ChatMessage.conversation_id == conversation.id).order_by(ChatMessage.position)
    ).scalars().all())


def delete_conversation(db: Session, conversation: ChatConversation) -> None:
    db.query(ChatMessage).filter(ChatMessage.conversation_id == conversation.id).delete()
    db.delete(conversation)
    db.commit()


def send_message(db: Session, user: User, content: str, conversation_id: uuid.UUID | None):
    if conversation_id:
        conv = get_conversation(db, user, conversation_id)
    else:
        title = content.strip()[:60] + ("…" if len(content.strip()) > 60 else "")
        conv = ChatConversation(user_id=user.id, title=title)
        db.add(conv)
        db.flush()

    history = [{"role": m.role, "content": m.content} for m in list_messages(db, conv)]
    next_pos = (db.execute(
        select(func.max(ChatMessage.position)).where(ChatMessage.conversation_id == conv.id)
    ).scalar() or 0) + 1

    answer, mode, sources = generate_reply(content, history)

    user_msg = ChatMessage(conversation_id=conv.id, position=next_pos, role="user", content=content, sources=[])
    bot_msg = ChatMessage(conversation_id=conv.id, position=next_pos + 1, role="assistant", content=answer, mode=mode, sources=sources)
    db.add_all([user_msg, bot_msg])
    conv.title = conv.title  # touch: keeps updated_at fresh so recent chats sort first
    db.commit()
    db.refresh(user_msg)
    db.refresh(bot_msg)
    return conv, user_msg, bot_msg
