"""
Phase 9 — chatbot (RAG). The real Gemini API is never called in tests:
it's replaced by fakes, so tests are free, fast and don't need a key.
"""
import pytest

from tests.conftest import register_and_login


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def send(client, token, content, conversation_id=None):
    body = {"content": content}
    if conversation_id:
        body["conversation_id"] = conversation_id
    return client.post("/api/v1/chat/messages", json=body, headers=auth(token))


class FakeProvider:
    name = "fake"

    def __init__(self, answer="Eczema is a common, non-contagious skin condition.", error=None):
        self.answer, self.error, self.calls = answer, error, []

    def generate(self, system_prompt, messages):
        self.calls.append((system_prompt, messages))
        if self.error:
            raise self.error
        return self.answer


@pytest.fixture()
def fake_provider(monkeypatch):
    import app.services.chat.providers as providers

    provider = FakeProvider()
    monkeypatch.setattr(providers, "get_provider", lambda: provider)
    return provider


# --- Retrieval ---------------------------------------------------------

@pytest.mark.parametrize("question, expected_source", [
    ("I have a red ring-shaped itchy rash, is it ringworm?", "fungal-infections.md"),
    ("how do I treat eczema", "eczema.md"),
    ("my mole changed colour and is bleeding", "skin-cancer.md"),
    ("how often should I reapply sunscreen", "skincare-sun-protection.md"),
    ("itchy welts after eating nuts", "hives.md"),
])
def test_retrieval_finds_the_right_topic(question, expected_source):
    from app.services.chat.knowledge_base import search

    assert search(question)[0].source == expected_source


@pytest.mark.parametrize("question", ["who won the cricket match", "write me python code", "hi"])
def test_retrieval_returns_nothing_for_off_topic_questions(question):
    from app.services.chat.knowledge_base import search

    assert search(question) == []


# --- Answer modes --------------------------------------------------------

def test_without_api_key_answers_from_knowledge_base(client):
    token = register_and_login(client)
    resp = send(client, token, "what causes acne?")
    assert resp.status_code == 200
    bot = resp.json()["assistant_message"]
    assert bot["mode"] == "knowledge_base"
    assert "acne" in bot["content"].lower()
    assert bot["sources"] and bot["sources"][0]["title"] == "Acne"


def test_with_provider_answers_with_ai_grounded_in_notes(client, fake_provider):
    token = register_and_login(client)
    bot = send(client, token, "how do I treat eczema?").json()["assistant_message"]
    assert bot["mode"] == "ai"
    assert bot["content"] == fake_provider.answer

    system_prompt, messages = fake_provider.calls[0]
    assert "Never diagnose" in system_prompt
    # the retrieved notes are passed to the model alongside the question
    assert "Reference notes" in messages[-1]["content"]
    assert "emollients" in messages[-1]["content"]


def test_ai_failure_falls_back_to_knowledge_base(client, monkeypatch):
    import app.services.chat.providers as providers

    failing = FakeProvider(error=providers.LLMProviderError("rate limit"))
    monkeypatch.setattr(providers, "get_provider", lambda: failing)
    token = register_and_login(client)
    resp = send(client, token, "is psoriasis contagious?")
    assert resp.status_code == 200
    assert resp.json()["assistant_message"]["mode"] == "knowledge_base"


def test_off_topic_question_is_redirected_without_calling_ai(client, fake_provider):
    token = register_and_login(client)
    bot = send(client, token, "what is the capital of France?").json()["assistant_message"]
    assert bot["mode"] == "out_of_scope"
    assert fake_provider.calls == []


# --- Safety ---------------------------------------------------------------

def test_emergency_gets_fixed_response_and_never_reaches_ai(client, fake_provider):
    token = register_and_login(client)
    bot = send(client, token, "I got hives and now my throat is closing and I can't breathe").json()["assistant_message"]
    assert bot["mode"] == "emergency"
    assert "112" in bot["content"]
    assert fake_provider.calls == []


def test_self_harm_message_gets_support_response(client, fake_provider):
    token = register_and_login(client)
    bot = send(client, token, "my acne is so bad I want to kill myself").json()["assistant_message"]
    assert bot["mode"] == "emergency"
    assert "14416" in bot["content"]
    assert fake_provider.calls == []


# --- Conversations ---------------------------------------------------------

def test_conversation_is_saved_and_listed_in_order(client):
    token = register_and_login(client)
    first = send(client, token, "what causes acne?").json()
    conv_id = first["conversation_id"]
    send(client, token, "how is it treated?", conversation_id=conv_id)

    convs = client.get("/api/v1/chat/conversations", headers=auth(token)).json()
    assert len(convs) == 1 and convs[0]["title"] == "what causes acne?"

    msgs = client.get(f"/api/v1/chat/conversations/{conv_id}/messages", headers=auth(token)).json()
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]
    assert msgs[2]["content"] == "how is it treated?"


def test_follow_up_question_keeps_topic(client):
    """'How is it treated?' contains no topic word: retrieval must use
    the previous question to stay on acne."""
    token = register_and_login(client)
    conv_id = send(client, token, "what causes acne?").json()["conversation_id"]
    bot = send(client, token, "how is it treated?", conversation_id=conv_id).json()["assistant_message"]
    assert bot["sources"][0] == {"title": "Acne", "section": "Treatment options"}


def test_off_topic_question_inside_existing_chat_is_redirected(client):
    """Regression: an off-topic question in an ongoing chat used to be
    searched together with the previous question, and got its answer."""
    token = register_and_login(client)
    conv_id = send(client, token, "I have a red ring-shaped itchy rash").json()["conversation_id"]
    bot = send(client, token, "who won the cricket match?", conversation_id=conv_id).json()["assistant_message"]
    assert bot["mode"] == "out_of_scope"


def test_topic_change_inside_existing_chat_uses_new_topic(client):
    token = register_and_login(client)
    conv_id = send(client, token, "what causes acne?").json()["conversation_id"]
    bot = send(client, token, "how do I treat eczema?", conversation_id=conv_id).json()["assistant_message"]
    assert bot["sources"][0]["title"] == "Eczema (atopic dermatitis)"


def test_generic_follow_up_keeps_topic(client):
    """'What are the symptoms?' names no topic, so it stays on psoriasis."""
    token = register_and_login(client)
    conv_id = send(client, token, "tell me about psoriasis").json()["conversation_id"]
    bot = send(client, token, "what are the symptoms?", conversation_id=conv_id).json()["assistant_message"]
    assert bot["sources"][0]["title"] == "Psoriasis"


def test_users_cannot_read_or_post_to_others_conversations(client):
    owner = register_and_login(client, email="owner@example.com")
    conv_id = send(client, owner, "what causes acne?").json()["conversation_id"]
    intruder = register_and_login(client, email="intruder@example.com")

    assert client.get(f"/api/v1/chat/conversations/{conv_id}/messages", headers=auth(intruder)).status_code == 404
    assert send(client, intruder, "hello", conversation_id=conv_id).status_code == 404
    assert client.get("/api/v1/chat/conversations", headers=auth(intruder)).json() == []


def test_delete_conversation(client):
    token = register_and_login(client)
    conv_id = send(client, token, "what causes acne?").json()["conversation_id"]
    assert client.delete(f"/api/v1/chat/conversations/{conv_id}", headers=auth(token)).status_code == 204
    assert client.get("/api/v1/chat/conversations", headers=auth(token)).json() == []


def test_message_validation_and_auth(client):
    token = register_and_login(client)
    assert send(client, token, "").status_code == 422
    assert send(client, token, "x" * 1001).status_code == 422
    assert client.post("/api/v1/chat/messages", json={"content": "hi"}).status_code == 401


# --- Gemini provider (HTTP layer, with httpx faked) ------------------------

class FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code, self._payload, self.text = status_code, payload, text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def test_gemini_request_format_and_answer_parsing(monkeypatch):
    import app.services.chat.providers as providers

    captured = {}

    def fake_post(url, headers, json, timeout):
        captured.update(url=url, headers=headers, json=json)
        return FakeResponse(200, {"candidates": [{"content": {"parts": [{"text": "Hello "}, {"text": "there"}]}}]})

    monkeypatch.setattr(providers.httpx, "post", fake_post)
    answer = providers.GeminiProvider("secret-key", "gemini-test").generate(
        "SYSTEM", [{"role": "user", "content": "Q1"}, {"role": "assistant", "content": "A1"}, {"role": "user", "content": "Q2"}]
    )
    assert answer == "Hello there"
    assert "gemini-test" in captured["url"] and "secret-key" not in captured["url"]  # key goes in a header
    assert captured["headers"]["x-goog-api-key"] == "secret-key"
    assert captured["json"]["system_instruction"]["parts"][0]["text"] == "SYSTEM"
    assert [c["role"] for c in captured["json"]["contents"]] == ["user", "model", "user"]


@pytest.mark.parametrize("response", [
    FakeResponse(429, text="quota"),
    FakeResponse(500, text="boom"),
    FakeResponse(200, {"candidates": []}),  # e.g. blocked by safety filters
])
def test_gemini_errors_raise_provider_error(monkeypatch, response):
    import app.services.chat.providers as providers

    monkeypatch.setattr(providers.httpx, "post", lambda *a, **k: response)
    with pytest.raises(providers.LLMProviderError):
        providers.GeminiProvider("k", "m").generate("S", [{"role": "user", "content": "Q"}])


def test_provider_is_off_without_key_and_on_with_key(monkeypatch):
    import app.services.chat.providers as providers

    monkeypatch.setattr(providers.settings, "GEMINI_API_KEY", "")
    assert providers.get_provider() is None
    monkeypatch.setattr(providers.settings, "GEMINI_API_KEY", "abc")
    assert providers.get_provider().name == "gemini"
