from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


InputMode = Literal["text", "voice"]
OutputMode = Literal["text", "voice", "both"]
TextProvider = Literal["ollama", "openai", "anthropic", "openrouter"]
TTSProvider = Literal["orpheus", "elevenlabs", "windows_sapi"]
VisionProvider = Literal["ollama", "openai", "openrouter"]
MemoryKind = Literal[
    "user_model",
    "project_model",
    "episodic_event",
    "relationship_signal",
    "personality_profile",
    "self_model",
    "fashion_preference",
    "wardrobe_model",
    "style_reference",
    "media_memory",
]
ReflectionCandidateStatus = Literal["pending", "approved", "rejected"]


class TextProviderStatus(BaseModel):
    name: TextProvider
    label: str
    available: bool
    default_model: str
    models: list[str]
    requires_api_key: bool = False
    detail: str | None = None


class VoiceOption(BaseModel):
    id: str
    label: str
    culture: str | None = None


class TTSProviderStatus(BaseModel):
    name: TTSProvider
    label: str
    available: bool
    default_voice: str | None = None
    voices: list[VoiceOption] = Field(default_factory=list)
    requires_api_key: bool = False
    detail: str | None = None


class VisionProviderStatus(BaseModel):
    name: VisionProvider
    label: str
    available: bool
    default_model: str
    models: list[str] = Field(default_factory=list)
    requires_api_key: bool = False
    detail: str | None = None


class ChatRequest(BaseModel):
    content: str = Field(min_length=1)
    session_id: str | None = None
    input_mode: InputMode = "text"
    output_mode: OutputMode = "text"
    provider: TextProvider | None = None
    model: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    user_message_id: int
    assistant_message_id: int
    content: str
    input_mode: InputMode
    output_mode: OutputMode
    model: str
    provider: TextProvider
    tokens_used: int | None = None


class HealthResponse(BaseModel):
    app: str
    database_path: str
    text_provider: TextProvider
    text_providers: list[TextProviderStatus]
    ollama_available: bool
    ollama_models: list[str]
    tts_provider: TTSProvider
    tts_providers: list[TTSProviderStatus]
    tts_available: bool
    tts_voices: list[str]
    vision_provider: VisionProvider
    vision_providers: list[VisionProviderStatus]


class MessageResponse(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    created_at: str
    tokens: int | None = None
    model: str | None = None
    audio_url: str | None = None
    audio_provider: str | None = None
    audio_voice: str | None = None


class SessionResponse(BaseModel):
    id: str
    title: str | None = None
    started_at: str
    updated_at: str
    ended_at: str | None = None
    summary: str | None = None
    message_count: int


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    provider: TTSProvider | None = None
    voice: str | None = None
    message_id: int | None = None


class TTSResponse(BaseModel):
    audio_id: str
    audio_url: str
    provider: str
    voice: str | None = None
    message_id: int | None = None


class MemoryItemCreate(BaseModel):
    kind: MemoryKind
    key: str = Field(min_length=1, max_length=160)
    value: str = Field(min_length=1, max_length=4000)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    source: str | None = Field(default=None, max_length=80)
    source_id: str | None = Field(default=None, max_length=120)


class MemoryItemUpdate(BaseModel):
    kind: MemoryKind | None = None
    key: str | None = Field(default=None, min_length=1, max_length=160)
    value: str | None = Field(default=None, min_length=1, max_length=4000)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    source: str | None = Field(default=None, max_length=80)
    source_id: str | None = Field(default=None, max_length=120)


class MemoryItemResponse(BaseModel):
    id: int
    kind: MemoryKind
    key: str
    value: str
    confidence: float
    source: str | None = None
    source_id: str | None = None
    created_at: str
    updated_at: str
    deleted_at: str | None = None


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=160)
    gender_identity: str | None = Field(default=None, max_length=160)
    age_range: str | None = Field(default=None, max_length=80)
    city: str | None = Field(default=None, max_length=220)
    height: str | None = Field(default=None, max_length=80)
    body_notes: str | None = Field(default=None, max_length=1000)
    size_tops: str | None = Field(default=None, max_length=160)
    size_bottoms: str | None = Field(default=None, max_length=160)
    size_shoes: str | None = Field(default=None, max_length=160)
    fit_preferences: str | None = Field(default=None, max_length=1000)
    favorite_colors: str | None = Field(default=None, max_length=500)
    avoided_colors: str | None = Field(default=None, max_length=500)
    style_keywords: str | None = Field(default=None, max_length=1000)
    primary_occasion: str | None = Field(default=None, max_length=500)
    style_focus: str | None = Field(default=None, max_length=500)
    comfort_notes: str | None = Field(default=None, max_length=1000)
    budget_notes: str | None = Field(default=None, max_length=1000)
    privacy_notes: str | None = Field(default=None, max_length=1000)


class ProfileResponse(ProfileUpdate):
    display_name: str = ""
    gender_identity: str = ""
    age_range: str = ""
    city: str = ""
    height: str = ""
    body_notes: str = ""
    size_tops: str = ""
    size_bottoms: str = ""
    size_shoes: str = ""
    fit_preferences: str = ""
    favorite_colors: str = ""
    avoided_colors: str = ""
    style_keywords: str = ""
    primary_occasion: str = ""
    style_focus: str = ""
    comfort_notes: str = ""
    budget_notes: str = ""
    privacy_notes: str = ""
    updated_at: str | None = None


class WardrobeItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    category: str = Field(min_length=1, max_length=120)
    subcategory: str | None = Field(default=None, max_length=120)
    colors: list[str] = Field(default_factory=list, max_length=16)
    material: str | None = Field(default=None, max_length=120)
    brand: str | None = Field(default=None, max_length=120)
    size_label: str | None = Field(default=None, max_length=80)
    fit: str | None = Field(default=None, max_length=120)
    season: str | None = Field(default=None, max_length=120)
    occasions: list[str] = Field(default_factory=list, max_length=20)
    style_tags: list[str] = Field(default_factory=list, max_length=24)
    notes: str | None = Field(default=None, max_length=2000)
    favorite: bool = False
    source: str | None = Field(default=None, max_length=80)
    source_id: str | None = Field(default=None, max_length=120)


class WardrobeItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=180)
    category: str | None = Field(default=None, min_length=1, max_length=120)
    subcategory: str | None = Field(default=None, max_length=120)
    colors: list[str] | None = Field(default=None, max_length=16)
    material: str | None = Field(default=None, max_length=120)
    brand: str | None = Field(default=None, max_length=120)
    size_label: str | None = Field(default=None, max_length=80)
    fit: str | None = Field(default=None, max_length=120)
    season: str | None = Field(default=None, max_length=120)
    occasions: list[str] | None = Field(default=None, max_length=20)
    style_tags: list[str] | None = Field(default=None, max_length=24)
    notes: str | None = Field(default=None, max_length=2000)
    favorite: bool | None = None
    source: str | None = Field(default=None, max_length=80)
    source_id: str | None = Field(default=None, max_length=120)


class WardrobeItemResponse(BaseModel):
    id: int
    name: str
    category: str
    subcategory: str | None = None
    colors: list[str] = Field(default_factory=list)
    material: str | None = None
    brand: str | None = None
    size_label: str | None = None
    fit: str | None = None
    season: str | None = None
    occasions: list[str] = Field(default_factory=list)
    style_tags: list[str] = Field(default_factory=list)
    notes: str | None = None
    favorite: bool = False
    source: str | None = None
    source_id: str | None = None
    image_count: int = 0
    created_at: str
    updated_at: str
    deleted_at: str | None = None


class WardrobeImageUpload(BaseModel):
    data_url: str = Field(min_length=20)
    original_name: str | None = Field(default=None, max_length=240)
    item_id: int | None = None


class WardrobeImageUpdate(BaseModel):
    item_id: int | None = None
    analysis: str | None = Field(default=None, max_length=8000)


class WardrobeImageResponse(BaseModel):
    id: int
    item_id: int | None = None
    image_url: str
    thumbnail_url: str | None = None
    original_name: str | None = None
    mime_type: str | None = None
    width: int | None = None
    height: int | None = None
    analysis: str | None = None
    created_at: str
    deleted_at: str | None = None


class VisionAnalyzeRequest(BaseModel):
    image_id: int
    prompt: str | None = Field(default=None, max_length=2000)
    provider: VisionProvider | None = None
    model: str | None = Field(default=None, max_length=160)
    save_memory: bool = True


class VisionAnalyzeResponse(BaseModel):
    image: WardrobeImageResponse
    provider: VisionProvider
    model: str
    analysis: str
    memory_item: MemoryItemResponse | None = None


class VisionCompareRequest(BaseModel):
    image_ids: list[int] = Field(min_length=2, max_length=6)
    prompt: str | None = Field(default=None, max_length=2000)
    provider: VisionProvider | None = None
    model: str | None = Field(default=None, max_length=160)
    save_memory: bool = True


class VisionCompareResponse(BaseModel):
    images: list[WardrobeImageResponse]
    provider: VisionProvider
    model: str
    analysis: str
    memory_item: MemoryItemResponse | None = None


WebSearchProvider = Literal["duckduckgo", "brave"]


class WebSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    provider: WebSearchProvider | None = None
    limit: int | None = Field(default=None, ge=1, le=10)


class WebSearchResultResponse(BaseModel):
    title: str
    url: str
    snippet: str | None = None
    source: str


class WebSearchResponse(BaseModel):
    query: str
    provider: WebSearchProvider
    results: list[WebSearchResultResponse]


class StyleResearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    search_provider: WebSearchProvider | None = None
    search_limit: int | None = Field(default=None, ge=1, le=10)
    provider: TextProvider | None = None
    model: str | None = Field(default=None, max_length=160)


class StyleResearchResponse(BaseModel):
    query: str
    brief: str
    provider: TextProvider
    model: str
    search: WebSearchResponse


class OutfitPlanRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    web_query: str | None = Field(default=None, max_length=500)
    search_provider: WebSearchProvider | None = None
    search_limit: int | None = Field(default=None, ge=1, le=10)
    provider: TextProvider | None = None
    model: str | None = Field(default=None, max_length=160)


class OutfitPlanResponse(BaseModel):
    prompt: str
    plan: str
    provider: TextProvider
    model: str
    search: WebSearchResponse | None = None


class WardrobeExtractionDraft(BaseModel):
    source_image_id: int
    name: str = Field(min_length=1, max_length=180)
    category: str = Field(min_length=1, max_length=120)
    subcategory: str | None = Field(default=None, max_length=120)
    colors: list[str] = Field(default_factory=list, max_length=16)
    material: str | None = Field(default=None, max_length=120)
    brand: str | None = Field(default=None, max_length=120)
    size_label: str | None = Field(default=None, max_length=80)
    fit: str | None = Field(default=None, max_length=120)
    season: str | None = Field(default=None, max_length=120)
    occasions: list[str] = Field(default_factory=list, max_length=20)
    style_tags: list[str] = Field(default_factory=list, max_length=24)
    notes: str | None = Field(default=None, max_length=2000)
    favorite: bool = False
    confidence: float = Field(default=0.45, ge=0.0, le=1.0)
    source: str | None = Field(default="vision", max_length=80)
    source_id: str | None = Field(default=None, max_length=120)
    raw_analysis: str = Field(default="", max_length=8000)


class WardrobeImageExtractRequest(BaseModel):
    prompt: str | None = Field(default=None, max_length=2000)
    provider: VisionProvider | None = None
    model: str | None = Field(default=None, max_length=160)


class WardrobeImageExtractResponse(BaseModel):
    image: WardrobeImageResponse
    provider: VisionProvider
    model: str
    draft: WardrobeExtractionDraft
    raw_analysis: str


class ContextMessage(BaseModel):
    role: str
    content: str


class ContextPreviewResponse(BaseModel):
    intent: str
    intent_reasons: list[str]
    system_context: str
    memory_items: list[MemoryItemResponse]
    semantic_items: list[MemoryItemResponse] = Field(default_factory=list)
    messages: list[ContextMessage]


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    status: str = Field(default="active", max_length=60)
    next_actions: list[str] = Field(default_factory=list, max_length=20)


class SemanticStatusResponse(BaseModel):
    enabled: bool
    available: bool
    collection: str
    qdrant_url: str
    embedding_model: str
    detail: str | None = None


class SemanticIndexResponse(BaseModel):
    indexed: int
    skipped: int
    collection: str


class SemanticSearchResultResponse(BaseModel):
    score: float
    memory_item: MemoryItemResponse | None = None
    payload: dict


class ReflectionRunRequest(BaseModel):
    session_id: str = Field(min_length=1)
    provider: TextProvider | None = None
    model: str | None = Field(default=None, max_length=120)
    limit: int | None = Field(default=None, ge=4, le=80)


class ReflectionCandidateUpdate(BaseModel):
    kind: MemoryKind | None = None
    key: str | None = Field(default=None, min_length=1, max_length=160)
    value: str | None = Field(default=None, min_length=1, max_length=4000)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    rationale: str | None = Field(default=None, max_length=800)
    evidence: str | None = Field(default=None, max_length=1200)


class ReflectionCandidateResponse(BaseModel):
    id: int
    session_id: str | None = None
    kind: MemoryKind
    key: str
    value: str
    confidence: float
    rationale: str | None = None
    evidence: str | None = None
    source: str
    source_message_ids: list[int] = Field(default_factory=list)
    status: ReflectionCandidateStatus
    memory_item_id: int | None = None
    created_at: str
    updated_at: str
    reviewed_at: str | None = None


class ReflectionRunResponse(BaseModel):
    candidates: list[ReflectionCandidateResponse]
    skipped: int
    provider: TextProvider
    model: str
    source: str


class ReflectionReviewResponse(BaseModel):
    candidate: ReflectionCandidateResponse
    memory_item: MemoryItemResponse | None = None


class SystemStatusResponse(BaseModel):
    app: str
    project_root: str
    data_dir: str
    database_path: str
    database_exists: bool
    database_size_bytes: int
    audio_dir: str
    media_dir: str
    backups_dir: str
    logs_dir: str
    counts: dict[str, int]
    configured: dict[str, Any]


class SystemBackupResponse(BaseModel):
    path: str
    size_bytes: int
    created_at: str


class SystemLogFileResponse(BaseModel):
    name: str
    path: str
    size_bytes: int
    modified_at: str | None = None


class SystemLogTailResponse(BaseModel):
    name: str
    content: str
    lines: int
    truncated: bool
