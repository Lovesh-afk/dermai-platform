"""
Safety checks that run BEFORE any AI is involved. An emergency must get
the same correct, immediate answer every time — so these responses are
fixed text, never generated, and they work even with no API key.

Matching is simple phrase lookup: it errs on the side of caution, and a
false alarm costs far less than a missed emergency.
"""
import re

EMERGENCY_PHRASES = [
    "can't breathe", "cant breathe", "cannot breathe", "difficulty breathing", "trouble breathing",
    "hard to breathe", "short of breath", "throat is closing", "throat closing", "throat swelling",
    "swollen throat", "tongue swelling", "swollen tongue", "lips swelling", "swollen lips",
    "face swelling", "swollen face", "anaphylaxis", "anaphylactic", "chest pain", "fainted", "fainting",
    "passed out", "skin peeling off", "skin is peeling off",
]

SELF_HARM_PHRASES = [
    "suicide", "suicidal", "kill myself", "end my life", "want to die", "self harm", "self-harm",
    "hurt myself", "harm myself", "cut myself", "no reason to live",
]

EMERGENCY_RESPONSE = (
    "This could be a medical emergency. Please call your local emergency number now "
    "(112 in India and Europe, 911 in the US) or go to the nearest emergency department.\n\n"
    "Swelling of the face, lips, tongue or throat, or difficulty breathing, can be signs of a "
    "severe allergic reaction (anaphylaxis). If you have an adrenaline (epinephrine) auto-injector, "
    "use it as directed. Please don't wait for an online answer."
)

SELF_HARM_RESPONSE = (
    "I'm really sorry you're feeling this way. You deserve support right now, and you don't have "
    "to handle this alone.\n\n"
    "If you might act on these thoughts or are in danger, please call your local emergency number "
    "now (112 in India). In India you can also call Tele-MANAS on 14416, free and available 24/7, "
    "to talk to a trained counsellor. If possible, reach out to someone you trust and let them "
    "know how you're feeling."
)


def _normalise(text: str) -> str:
    text = text.lower().replace("’", "'")
    return re.sub(r"\s+", " ", text)


def check_message(text: str) -> str | None:
    """Returns a fixed safety response if the message needs one, else None."""
    t = _normalise(text)
    if any(p in t for p in SELF_HARM_PHRASES):
        return SELF_HARM_RESPONSE
    if any(p in t for p in EMERGENCY_PHRASES):
        return EMERGENCY_RESPONSE
    return None
