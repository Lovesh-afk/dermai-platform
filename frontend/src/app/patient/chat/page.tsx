"use client";

import { FormEvent, ReactNode, useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth";
import { useAuthedData } from "@/lib/useAuthedData";
import { chatApi, ApiError, ChatMessage } from "@/lib/api";
import { Alert, Button, Spinner } from "@/components/ui";

const MAX_LENGTH = 1000; // mirrors the backend limit

const STARTER_QUESTIONS = [
  "What causes acne?",
  "How can I tell if a mole is worrying?",
  "Is ringworm contagious?",
  "How often should I reapply sunscreen?",
];

export default function ChatPage() {
  const { accessToken } = useAuth();
  const { data: conversations, refetch: refetchConversations } = useAuthedData((t) => chatApi.conversations(t));
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Keep the newest message in view
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  async function openConversation(id: string) {
    if (!accessToken) return;
    setActiveId(id);
    setError(null);
    setLoadingMessages(true);
    try {
      setMessages(await chatApi.messages(accessToken, id));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't load this conversation.");
    } finally {
      setLoadingMessages(false);
    }
  }

  function startNewChat() {
    setActiveId(null);
    setMessages([]);
    setError(null);
  }

  async function sendMessage(text: string) {
    const content = text.trim();
    if (!content || !accessToken || sending) return;
    setSending(true);
    setError(null);
    setInput("");
    // Show the question immediately; it's replaced by the saved version below
    const pending: ChatMessage = { id: "pending", role: "user", content, mode: null, sources: [], created_at: new Date().toISOString() };
    setMessages((prev) => [...prev, pending]);
    try {
      const turn = await chatApi.send(accessToken, content, activeId ?? undefined);
      setMessages((prev) => [...prev.filter((m) => m.id !== "pending"), turn.user_message, turn.assistant_message]);
      if (!activeId) {
        setActiveId(turn.conversation_id);
      }
      refetchConversations();
    } catch (err) {
      setMessages((prev) => prev.filter((m) => m.id !== "pending"));
      setInput(content); // give the text back so nothing is lost
      setError(err instanceof ApiError ? err.message : "Couldn't send your message. Please try again.");
    } finally {
      setSending(false);
    }
  }

  async function deleteConversation(id: string) {
    if (!accessToken) return;
    try {
      await chatApi.remove(accessToken, id);
      if (id === activeId) startNewChat();
      refetchConversations();
    } catch {
      setError("Couldn't delete that conversation.");
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    sendMessage(input);
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="font-display text-3xl text-ink">Ask DermAI</h1>
        <p className="mt-1 text-ink-soft">
          General information about skin, hair and nail health. Not a diagnosis; for your own skin, see a dermatologist.
        </p>
      </div>

      <div className="grid grid-cols-[14rem_1fr] gap-4">
        {/* Conversation list */}
        <aside className="flex flex-col gap-2">
          <Button size="sm" onClick={startNewChat}>New chat</Button>
          <ul className="flex flex-col gap-1" aria-label="Past conversations">
            {conversations?.map((c) => (
              <li key={c.id} className="group flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => openConversation(c.id)}
                  className={`flex-1 truncate rounded-lg px-3 py-2 text-left text-sm ${
                    c.id === activeId ? "bg-pine-100 text-ink" : "text-ink-soft hover:bg-sage-100"
                  }`}
                  title={c.title}
                >
                  {c.title}
                </button>
                <button
                  type="button"
                  onClick={() => deleteConversation(c.id)}
                  className="rounded px-1.5 text-ink-soft opacity-0 hover:text-alert focus:opacity-100 group-hover:opacity-100"
                  aria-label={`Delete conversation: ${c.title}`}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        </aside>

        {/* Chat panel */}
        <section className="flex h-[32rem] flex-col rounded-card border border-sage-100 bg-white">
          <div className="flex-1 overflow-y-auto p-5" aria-live="polite">
            {loadingMessages ? (
              <Spinner className="h-5 w-5 text-pine-600" />
            ) : messages.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center gap-4 text-center">
                <p className="font-display text-xl text-ink">How can I help?</p>
                <div className="flex max-w-md flex-wrap justify-center gap-2">
                  {STARTER_QUESTIONS.map((q) => (
                    <button
                      key={q}
                      type="button"
                      onClick={() => sendMessage(q)}
                      className="rounded-full bg-sage-100 px-3 py-1.5 text-sm text-ink hover:bg-sage-200"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                {messages.map((m) => (
                  <MessageBubble key={m.id} message={m} />
                ))}
                {sending && (
                  <p className="flex items-center gap-2 text-sm text-ink-soft">
                    <Spinner className="h-4 w-4 text-pine-600" /> Thinking…
                  </p>
                )}
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {error && (
            <div className="px-5 pb-2">
              <Alert>{error}</Alert>
            </div>
          )}

          <form onSubmit={handleSubmit} className="flex gap-2 border-t border-sage-100 p-3">
            <label htmlFor="chat-input" className="sr-only">Your question</label>
            <input
              id="chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              maxLength={MAX_LENGTH}
              placeholder="Ask about a skin, hair or nail concern…"
              className="flex-1 rounded-full border border-sage-200 px-4 py-2 text-sm text-ink focus:border-pine-600"
              disabled={sending}
            />
            <Button type="submit" disabled={sending || !input.trim()}>Send</Button>
          </form>
        </section>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="ml-auto max-w-[80%] rounded-2xl rounded-br-sm bg-pine-600 px-4 py-2.5 text-sm text-porcelain">
        {message.content}
      </div>
    );
  }

  const isEmergency = message.mode === "emergency";
  return (
    <div
      className={`max-w-[85%] rounded-2xl rounded-bl-sm px-4 py-3 text-sm ${
        isEmergency ? "border border-alert bg-alert-soft text-ink" : "bg-sage-50 text-ink"
      }`}
    >
      {isEmergency && <p className="mb-1 font-semibold text-alert">Important</p>}
      <FormattedText text={message.content} />

      {message.sources.length > 0 && (
        <p className="mt-3 text-xs text-ink-soft">
          Based on: {Array.from(new Set(message.sources.map((s) => s.title))).join(", ")}
        </p>
      )}
      {message.mode === "knowledge_base" && (
        <p className="mt-1 text-xs text-ink-soft">Answered directly from the DermAI knowledge base.</p>
      )}
    </div>
  );
}

/** Minimal formatting for answers: paragraphs, "- " bullet lists and
 * **bold**. Deliberately not a full markdown parser: the model is told
 * to stick to these, and rendering plain text keeps it safe from HTML injection. */
function FormattedText({ text }: { text: string }) {
  const blocks = text.split(/\n{2,}/);
  return (
    <div className="flex flex-col gap-2">
      {blocks.map((block, i) => {
        const lines = block.split("\n");
        if (lines.every((l) => /^\s*[-*] /.test(l))) {
          return (
            <ul key={i} className="ml-4 list-disc">
              {lines.map((l, j) => (
                <li key={j}>{withBold(l.replace(/^\s*[-*] /, ""))}</li>
              ))}
            </ul>
          );
        }
        return (
          <p key={i} className="whitespace-pre-line">
            {withBold(block)}
          </p>
        );
      })}
    </div>
  );
}

function withBold(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? <strong key={i}>{part.slice(2, -2)}</strong> : part
  );
}
