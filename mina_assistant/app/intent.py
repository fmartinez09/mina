from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


IntentName = str


@dataclass(frozen=True)
class IntentResult:
    name: IntentName
    reasons: list[str] = field(default_factory=list)


class IntentClassifier:
    def classify(self, content: str) -> IntentResult:
        text = _normalize(content)
        if not text:
            return IntentResult("general_chat", ["empty_or_whitespace"])

        if _has(text, r"\b(recuerda|remember|memoria|memory)\b") or "que sabes de mi" in text:
            return IntentResult("memory_query", ["memory_keyword"])

        if _has(
            text,
            (
                r"\b(moda|fashion|outfit|look|ropa|guardarropa|wardrobe|closet|pantalon|"
                r"pantalones|jeans|chaqueta|jacket|perfumes?|fragancias?|fragrance)\b"
            ),
        ):
            return IntentResult("fashion_context", ["fashion_keyword"])

        if _has(
            text,
            (
                r"\b(personalidad|personality|autoimagen|self model|rol de mina|"
                r"como me respondes|como quiero que respondas|tono|humor|formalidad|"
                r"proactividad|iniciativa)\b"
            ),
        ):
            return IntentResult("personality_context", ["personality_keyword"])

        if _has(text, r"\b(proyecto|project|hito|milestone|pendiente|next action|seguimos|dejamos)\b"):
            return IntentResult("project_context", ["project_keyword"])

        if _has(text, r"\b(prefiero|me gusta|soy|mi estilo|my preference|i prefer|i like|i am)\b"):
            return IntentResult("personal_context", ["personal_keyword"])

        if _has(text, r"\b(voz|audio|tts|orpheus|elevenlabs|whisper|microfono|voice)\b"):
            return IntentResult("voice_or_tts", ["voice_keyword"])

        if _has(text, r"\b(tarea|task|hacer|todo|accion|action)\b"):
            return IntentResult("task_or_next_action", ["task_keyword"])

        return IntentResult("general_chat", ["fallback"])


def _normalize(content: str) -> str:
    normalized = unicodedata.normalize("NFKD", content)
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", without_accents).strip().lower()


def _has(content: str, pattern: str) -> bool:
    return re.search(pattern, content, flags=re.IGNORECASE) is not None
