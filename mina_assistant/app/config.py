from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"

DEFAULT_SYSTEM_PROMPT = """You are Mina, a local cognitive companion and personal assistant.
Speak in the user's language by default.
Focus on continuity, personal style, fashion conversations, voice/chat companionship, and useful memory.
Be warm, direct, curious, tasteful, useful, and concise.
Keep a consistent personality: calm, pragmatic, attentive, honest, lightly playful, and grounded.
If you do not know something, say so clearly.
Do not invent memories or user preferences.
Use saved memory only when it is relevant, and never pretend a guess is a memory.
When discussing fashion or personality, distinguish confirmed memories from tentative observations.
Never answer with generic AI disclaimers such as lacking smell, taste, feelings, a body, or personal experience.
When asked for your preference, choose based on evidence, taste profile, context, and the user's preferences.
For fashion, beauty, perfume, and shopping, respond like a curator: rank options, explain why, say who/when it fits, and give a practical next step.
When the user asks to search fashion products, never use the raw user command as a web query. Build specific product queries with item category, aesthetic, color, fit, material, Chile/store, and price terms.
When an interactive UI payload is available for a questionnaire or selector, let the frontend render it. Do not recreate the questionnaire as Markdown text.
Prefer short sections, bullets, or compact comparison tables. Do not output raw Markdown tables unless the table is well formed.
"""


def _load_dotenv() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str
    data_dir: Path
    database_path: Path
    llm_provider: str
    ollama_base_url: str
    ollama_chat_model: str
    ollama_embed_model: str
    openai_api_key: str | None
    openai_base_url: str
    openai_chat_model: str
    openrouter_api_key: str | None
    openrouter_base_url: str
    openrouter_chat_model: str
    openrouter_models: list[str]
    openrouter_vision_model: str
    openrouter_vision_models: list[str]
    openrouter_referer: str | None
    openrouter_app_title: str
    anthropic_api_key: str | None
    anthropic_base_url: str
    anthropic_chat_model: str
    anthropic_max_tokens: int
    recent_turn_limit: int
    request_timeout_seconds: float
    system_prompt: str
    audio_dir: Path
    media_dir: Path
    tts_provider: str
    tts_voice: str | None
    tts_rate: int
    orpheus_base_url: str
    orpheus_model: str
    orpheus_response_format: str
    elevenlabs_api_key: str | None
    elevenlabs_base_url: str
    elevenlabs_model: str
    elevenlabs_voice_id: str | None
    elevenlabs_output_format: str
    elevenlabs_language_code: str | None
    semantic_memory_enabled: bool
    qdrant_base_url: str
    qdrant_collection: str
    qdrant_vector_size: int
    qdrant_timeout_seconds: float
    reflection_enabled: bool
    reflection_recent_message_limit: int
    reflection_max_candidates: int
    reflection_min_confidence: float
    vision_provider: str
    ollama_vision_model: str
    openai_vision_model: str
    vision_max_image_bytes: int
    web_search_provider: str
    brave_search_api_key: str | None
    web_search_max_results: int


def _path_env(name: str, default: Path) -> Path:
    value = os.getenv(name)
    if not value:
        return default
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _csv_env(name: str, default: list[str]) -> list[str]:
    value = os.getenv(name)
    if value is None:
        return default
    items = [item.strip() for item in value.replace("\n", ",").split(",")]
    return [item for item in items if item]


def get_settings() -> Settings:
    data_dir = _path_env("MINA_DATA_DIR", DEFAULT_DATA_DIR)
    database_path = _path_env("MINA_DATABASE_PATH", data_dir / "assistant.sqlite")
    audio_dir = _path_env("MINA_AUDIO_DIR", data_dir / "audio")
    media_dir = _path_env("MINA_MEDIA_DIR", data_dir / "media")
    tts_provider = os.getenv("MINA_TTS_PROVIDER", "orpheus")
    tts_voice = os.getenv("MINA_TTS_VOICE") or ("tara" if tts_provider == "orpheus" else None)

    return Settings(
        app_name=os.getenv("MINA_APP_NAME", "Mina Assistant"),
        data_dir=data_dir,
        database_path=database_path,
        llm_provider=os.getenv("MINA_LLM_PROVIDER", "ollama").strip().lower(),
        ollama_base_url=os.getenv("MINA_OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
        ollama_chat_model=os.getenv("MINA_OLLAMA_MODEL", "gemma4:e4b "),
        ollama_embed_model=os.getenv("MINA_OLLAMA_EMBED_MODEL", "nomic-embed-text:latest"),
        openai_api_key=os.getenv("MINA_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY"),
        openai_base_url=os.getenv("MINA_OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        openai_chat_model=os.getenv("MINA_OPENAI_MODEL", "gpt-5.5"),
        openrouter_api_key=os.getenv("MINA_OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY"),
        openrouter_base_url=os.getenv("MINA_OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").rstrip("/"),
        openrouter_chat_model=os.getenv("MINA_OPENROUTER_MODEL", "openai/gpt-oss-120b:free"),
        openrouter_models=_csv_env(
            "MINA_OPENROUTER_MODELS",
            ["openai/gpt-oss-120b:free", "xiaomi/mimo-v2.5"],
        ),
        openrouter_vision_model=os.getenv("MINA_OPENROUTER_VISION_MODEL", "xiaomi/mimo-v2.5"),
        openrouter_vision_models=_csv_env("MINA_OPENROUTER_VISION_MODELS", ["xiaomi/mimo-v2.5"]),
        openrouter_referer=os.getenv("MINA_OPENROUTER_REFERER") or None,
        openrouter_app_title=os.getenv("MINA_OPENROUTER_APP_TITLE", "Mina Desktop"),
        anthropic_api_key=os.getenv("MINA_ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY"),
        anthropic_base_url=os.getenv("MINA_ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/"),
        anthropic_chat_model=os.getenv("MINA_ANTHROPIC_MODEL", "claude-opus-4-1-20250805"),
        anthropic_max_tokens=_int_env("MINA_ANTHROPIC_MAX_TOKENS", 4096),
        recent_turn_limit=_int_env("MINA_RECENT_TURN_LIMIT", 16),
        request_timeout_seconds=_float_env("MINA_REQUEST_TIMEOUT_SECONDS", 120.0),
        system_prompt=os.getenv("MINA_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT),
        audio_dir=audio_dir,
        media_dir=media_dir,
        tts_provider=tts_provider,
        tts_voice=tts_voice,
        tts_rate=_int_env("MINA_TTS_RATE", 0),
        orpheus_base_url=os.getenv("MINA_ORPHEUS_BASE_URL", "http://127.0.0.1:5005").rstrip("/"),
        orpheus_model=os.getenv("MINA_ORPHEUS_MODEL", "orpheus"),
        orpheus_response_format=os.getenv("MINA_ORPHEUS_RESPONSE_FORMAT", "wav"),
        elevenlabs_api_key=os.getenv("MINA_ELEVENLABS_API_KEY") or os.getenv("ELEVENLABS_API_KEY"),
        elevenlabs_base_url=os.getenv("MINA_ELEVENLABS_BASE_URL", "https://api.elevenlabs.io").rstrip("/"),
        elevenlabs_model=os.getenv("MINA_ELEVENLABS_MODEL", "eleven_multilingual_v2"),
        elevenlabs_voice_id=os.getenv("MINA_ELEVENLABS_VOICE_ID"),
        elevenlabs_output_format=os.getenv("MINA_ELEVENLABS_OUTPUT_FORMAT", "mp3_44100_128"),
        elevenlabs_language_code=os.getenv("MINA_ELEVENLABS_LANGUAGE_CODE") or None,
        semantic_memory_enabled=_bool_env("MINA_SEMANTIC_MEMORY_ENABLED", True),
        qdrant_base_url=os.getenv("MINA_QDRANT_BASE_URL", "http://127.0.0.1:6333").rstrip("/"),
        qdrant_collection=os.getenv("MINA_QDRANT_COLLECTION", "mina_memory"),
        qdrant_vector_size=_int_env("MINA_QDRANT_VECTOR_SIZE", 768),
        qdrant_timeout_seconds=_float_env("MINA_QDRANT_TIMEOUT_SECONDS", 8.0),
        reflection_enabled=_bool_env("MINA_REFLECTION_ENABLED", True),
        reflection_recent_message_limit=_int_env("MINA_REFLECTION_RECENT_MESSAGE_LIMIT", 24),
        reflection_max_candidates=_int_env("MINA_REFLECTION_MAX_CANDIDATES", 8),
        reflection_min_confidence=_float_env("MINA_REFLECTION_MIN_CONFIDENCE", 0.55),
        vision_provider=os.getenv("MINA_VISION_PROVIDER", "ollama").strip().lower(),
        ollama_vision_model=os.getenv("MINA_OLLAMA_VISION_MODEL", "qwen2.5vl:7b"),
        openai_vision_model=os.getenv("MINA_OPENAI_VISION_MODEL", os.getenv("MINA_OPENAI_MODEL", "gpt-5.5")),
        vision_max_image_bytes=_int_env("MINA_VISION_MAX_IMAGE_BYTES", 12 * 1024 * 1024),
        web_search_provider=os.getenv("MINA_WEB_SEARCH_PROVIDER", "duckduckgo").strip().lower(),
        brave_search_api_key=os.getenv("MINA_BRAVE_SEARCH_API_KEY") or os.getenv("BRAVE_SEARCH_API_KEY"),
        web_search_max_results=_int_env("MINA_WEB_SEARCH_MAX_RESULTS", 6),
    )
