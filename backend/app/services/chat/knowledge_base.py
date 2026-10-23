"""
Retrieval half of RAG: finds the knowledge-base sections most relevant
to a question, using BM25 (the ranking formula behind classic search
engines like Elasticsearch/Lucene).

Why BM25 instead of vector embeddings:
  - Needs no API key and no extra service: works fully offline.
  - The knowledge base is small (~60 sections), where keyword ranking
    performs well, and results are easy to explain and debug.
  - Embeddings (e.g. pgvector) can replace search() later without
    changing any caller.

Each markdown file is one topic; each "## " section is one chunk.
"""
import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import snowballstemmer

KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "knowledge"

# BM25 tuning constants (standard defaults)
K1 = 1.5  # how quickly repeated terms stop adding score
B = 0.75  # how much long sections are penalised

# Below this score a match is treated as "not about our topics"
MIN_RELEVANCE_SCORE = 2.0

# A question word that appears in a topic's title ("eczema" in
# "Eczema (atopic dermatitis)") is strong evidence that topic is the
# subject, so title matches get extra weight.
TITLE_BOOST = 1.5

_stemmer = snowballstemmer.stemmer("english")

# Word forms the stemmer leaves apart but people use interchangeably:
# Snowball turns "treated" into "treat" but keeps "treatment" whole.
STEM_ALIASES = {"treatment": "treat", "cure": "treat", "remedi": "treat", "medicin": "medic"}

# Title words that describe a question rather than name a topic: "what
# are the symptoms?" or "is it itchy?" is a follow-up, not a new topic.
# (Stemmed forms, matching tokenize().)
GENERIC_TITLE_TERMS = {"symptom", "itch", "infect", "use", "urgent", "medic", "everyday", "chang", "protect"}

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "of", "to", "in", "on", "at", "for", "with", "by",
    "from", "is", "are", "was", "were", "be", "been", "it", "its", "this", "that", "these", "those",
    "i", "me", "my", "you", "your", "we", "our", "he", "she", "they", "them", "what", "which", "who",
    "how", "why", "when", "where", "do", "does", "did", "can", "could", "should", "would", "will",
    "have", "has", "had", "not", "no", "so", "as", "about", "get", "got", "any", "some", "there",
    "am", "very", "much", "many", "more", "most", "also", "just", "than", "then", "too", "into",
    "tell", "please", "know", "want", "need", "help", "thing", "things", "okay", "ok", "hi", "hello",
}


@dataclass(frozen=True)
class Chunk:
    source: str   # file name, e.g. "eczema.md"
    title: str    # topic title, e.g. "Eczema (atopic dermatitis)"
    section: str  # section heading, e.g. "Symptoms"
    text: str


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [_stem(w) for w in words if w not in STOPWORDS and len(w) > 1]


def _stem(word: str) -> str:
    """Snowball (Porter2) stemming, so "treat"/"treatment",
    "reapply"/"reapplied" and "rash"/"rashes" count as the same word."""
    stem = _stemmer.stemWord(word)
    return STEM_ALIASES.get(stem, stem)


def _load_chunks() -> list[Chunk]:
    chunks = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        if path.name == "README.md":
            continue
        content = path.read_text(encoding="utf-8")
        title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else path.stem
        for section in re.split(r"^## ", content, flags=re.MULTILINE)[1:]:
            heading, _, body = section.partition("\n")
            if body.strip():
                chunks.append(Chunk(path.name, title, heading.strip(), body.strip()))
    return chunks


class BM25Index:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        # Title + heading are indexed too, so "ringworm" matches the
        # fungal-infections note even in sections that never repeat the word.
        self.docs = [tokenize(f"{c.title} {c.section} {c.text}") for c in chunks]
        self.term_freqs = [Counter(d) for d in self.docs]
        self.title_terms = [set(tokenize(c.title)) for c in chunks]

        # Words that identify ONE topic (they appear in exactly one note's
        # title, e.g. "eczema", "ringworm"). Generic title words shared by
        # several notes, like "skin", don't count.
        titles_per_term = Counter(t for title in {c.title for c in chunks} for t in set(tokenize(title)))
        self.topic_terms = {t for t, n in titles_per_term.items() if n == 1} - GENERIC_TITLE_TERMS
        self.avg_len = sum(len(d) for d in self.docs) / max(len(self.docs), 1)
        doc_freq = Counter(term for d in self.docs for term in set(d))
        n = len(self.docs)
        # Rare terms (e.g. "ringworm") count far more than common ones (e.g. "skin")
        self.idf = {t: math.log(1 + (n - df + 0.5) / (df + 0.5)) for t, df in doc_freq.items()}

    def score(self, query_terms: list[str], i: int) -> float:
        tf, length = self.term_freqs[i], len(self.docs[i])
        total = 0.0
        for term in query_terms:
            if term in tf:
                f = tf[term]
                total += self.idf[term] * f * (K1 + 1) / (f + K1 * (1 - B + B * length / self.avg_len))
                if term in self.title_terms[i]:
                    total += TITLE_BOOST * self.idf[term]
        return total


@lru_cache(maxsize=1)
def get_index() -> BM25Index:
    """Built once per process; the notes only change on redeploy."""
    return BM25Index(_load_chunks())


def search(query: str, top_k: int = 3) -> list[Chunk]:
    """Most relevant sections, best first. Empty if nothing is relevant
    enough, which callers treat as an off-topic question."""
    index = get_index()
    terms = tokenize(query)
    if not terms:
        return []
    scored = sorted(((index.score(terms, i), i) for i in range(len(index.chunks))), reverse=True)
    return [index.chunks[i] for score, i in scored[:top_k] if score >= MIN_RELEVANCE_SCORE]


def names_a_topic(question: str) -> bool:
    """True if the question names a specific topic itself, e.g. "eczema"."""
    return any(t in get_index().topic_terms for t in tokenize(question))


def uses_known_terms(question: str) -> bool:
    """True if any word in the question appears anywhere in the notes.
    "who won the cricket match" -> False; "how is it treated" -> True."""
    return any(t in get_index().idf for t in tokenize(question))


def topic_words(text: str) -> str:
    """Just the topic-naming words of a text, e.g. "what causes acne?" -> "acne"."""
    index = get_index()
    words = re.findall(r"[a-z0-9]+", text.lower())
    return " ".join(w for w in words if _stem(w) in index.topic_terms)
