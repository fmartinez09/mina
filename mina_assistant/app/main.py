from __future__ import annotations

import argparse
import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from mina_assistant.app.chat_tools import ChatToolService
from mina_assistant.app.config import get_settings
from mina_assistant.app.context import ContextBuilder
from mina_assistant.app.db import MemoryConflictError, SQLiteStore
from mina_assistant.app.intent import IntentClassifier
from mina_assistant.app.llm import LLMError, LLMService
from mina_assistant.app.media import MediaError, MediaService
from mina_assistant.app.memory import MemoryService
from mina_assistant.app.orchestrator import AssistantOrchestrator
from mina_assistant.app.profile import ProfileService
from mina_assistant.app.reflection import ReflectionError, ReflectionService
from mina_assistant.app.schemas import (
    ChatRequest,
    ChatResponse,
    ContextPreviewResponse,
    HealthResponse,
    MemoryItemCreate,
    MemoryItemResponse,
    MemoryItemUpdate,
    MemoryKind,
    MessageResponse,
    ProfileResponse,
    ProfileUpdate,
    ProjectCreate,
    OutfitPlanRequest,
    OutfitPlanResponse,
    ReflectionCandidateResponse,
    ReflectionCandidateStatus,
    ReflectionCandidateUpdate,
    ReflectionReviewResponse,
    ReflectionRunRequest,
    ReflectionRunResponse,
    SemanticIndexResponse,
    SemanticSearchResultResponse,
    SemanticStatusResponse,
    SessionResponse,
    StyleResearchRequest,
    StyleResearchResponse,
    SystemBackupResponse,
    SystemLogFileResponse,
    SystemLogTailResponse,
    SystemStatusResponse,
    TTSRequest,
    TTSResponse,
    VisionAnalyzeRequest,
    VisionAnalyzeResponse,
    VisionCompareRequest,
    VisionCompareResponse,
    WardrobeImageExtractRequest,
    WardrobeImageExtractResponse,
    WardrobeItemCreate,
    WardrobeItemResponse,
    WardrobeItemUpdate,
    WardrobeImageResponse,
    WardrobeImageUpdate,
    WardrobeImageUpload,
    WebSearchRequest,
    WebSearchResponse,
)
from mina_assistant.app.semantic import SemanticMemoryError, SemanticMemoryService
from mina_assistant.app.style import StyleAssistantService
from mina_assistant.app.system import SystemService
from mina_assistant.app.tts import TTSError, TTSService
from mina_assistant.app.vision import VisionError, VisionService
from mina_assistant.app.wardrobe import WardrobeService
from mina_assistant.app.web_search import WebSearchError, WebSearchService


settings = get_settings()
STATIC_DIR = Path(__file__).resolve().parent / "static"
settings.audio_dir.mkdir(parents=True, exist_ok=True)
settings.media_dir.mkdir(parents=True, exist_ok=True)
db = SQLiteStore(settings.database_path)
llm = LLMService(settings)
memory_service = MemoryService(db)
profile_service = ProfileService(db=db, memory=memory_service)
wardrobe_service = WardrobeService(db=db, memory=memory_service)
media_service = MediaService(settings=settings, db=db)
vision_service = VisionService(settings)
web_search_service = WebSearchService(settings)
chat_tool_service = ChatToolService(
    db=db,
    profile=profile_service,
    web_search=web_search_service,
)
style_service = StyleAssistantService(
    db=db,
    llm=llm,
    profile=profile_service,
    web_search=web_search_service,
)
semantic_memory_service = SemanticMemoryService(settings=settings, db=db)
memory_index_lock = asyncio.Lock()
intent_classifier = IntentClassifier()
context_builder = ContextBuilder(
    settings=settings,
    db=db,
    memory=memory_service,
    intent_classifier=intent_classifier,
    semantic_memory=semantic_memory_service,
)
orchestrator = AssistantOrchestrator(
    settings=settings,
    db=db,
    llm=llm,
    memory=memory_service,
    context_builder=context_builder,
    semantic_memory=semantic_memory_service,
    chat_tools=chat_tool_service,
)
tts_service = TTSService(settings)
reflection_service = ReflectionService(
    settings=settings,
    db=db,
    llm=llm,
    memory=memory_service,
)
system_service = SystemService(settings=settings, db=db)


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.initialize()
    tts_service.initialize()
    media_service.initialize()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/audio", StaticFiles(directory=settings.audio_dir), name="audio")
app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    provider_statuses = await llm.provider_statuses()
    ollama_status = next(status for status in provider_statuses if status.name == "ollama")

    try:
        tts_statuses = await asyncio.to_thread(tts_service.provider_statuses)
        active_tts = next(
            (status for status in tts_statuses if status.name == settings.tts_provider),
            tts_statuses[0],
        )
        voices = [_voice_label(voice) for voice in active_tts.voices]
        tts_available = active_tts.available
    except TTSError:
        tts_statuses = []
        voices = []
        tts_available = False

    vision_statuses = await vision_service.provider_statuses()
    vision_provider = settings.vision_provider if settings.vision_provider in {"ollama", "openai", "openrouter"} else "ollama"

    return HealthResponse(
        app=settings.app_name,
        database_path=str(settings.database_path),
        text_provider=settings.llm_provider,
        text_providers=[status.__dict__ for status in provider_statuses],
        ollama_available=ollama_status.available,
        ollama_models=ollama_status.models,
        tts_provider=settings.tts_provider,
        tts_providers=[_tts_status_payload(status) for status in tts_statuses],
        tts_available=tts_available,
        tts_voices=voices,
        vision_provider=vision_provider,
        vision_providers=[status.__dict__ for status in vision_statuses],
    )


@app.get("/api/system/status", response_model=SystemStatusResponse)
async def system_status() -> dict:
    return system_service.status()


@app.post("/api/system/backup", response_model=SystemBackupResponse)
async def system_backup() -> SystemBackupResponse:
    backup = await asyncio.to_thread(system_service.create_backup)
    return SystemBackupResponse(**backup.__dict__)


@app.get("/api/system/logs", response_model=list[SystemLogFileResponse])
async def system_logs() -> list[dict]:
    return [log.__dict__ for log in system_service.list_logs()]


@app.get("/api/system/logs/tail", response_model=SystemLogTailResponse)
async def system_log_tail(name: str, lines: int = 200) -> SystemLogTailResponse:
    try:
        tail = system_service.tail_log(name, max_lines=max(20, min(lines, 500)))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SystemLogTailResponse(**tail.__dict__)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        result = await orchestrator.chat(
            request.content,
            session_id=request.session_id,
            input_mode=request.input_mode,
            output_mode=request.output_mode,
            provider=request.provider,
            model=request.model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ChatResponse(**result.__dict__)


@app.post("/api/tts", response_model=TTSResponse)
async def synthesize_tts(request: TTSRequest) -> TTSResponse:
    try:
        result = await asyncio.to_thread(
            tts_service.synthesize,
            request.text,
            provider=request.provider,
            voice=request.voice,
        )
    except TTSError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if request.message_id is not None:
        db.add_audio_output(
            message_id=request.message_id,
            audio_id=result.audio_id,
            audio_url=result.audio_url,
            provider=result.provider,
            voice=result.voice,
        )

    return TTSResponse(
        audio_id=result.audio_id,
        audio_url=result.audio_url,
        provider=result.provider,
        voice=result.voice,
        message_id=request.message_id,
    )


@app.get("/api/sessions", response_model=list[SessionResponse])
async def sessions(limit: int = 20) -> list[dict]:
    return db.list_sessions(limit=limit)


@app.get("/api/sessions/{session_id}/messages", response_model=list[MessageResponse])
async def messages(session_id: str) -> list[dict]:
    if not db.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Sesion no encontrada.")
    return db.list_messages(session_id)


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str) -> dict[str, bool]:
    if not db.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Sesion no encontrada.")
    return {"deleted": True}


@app.get("/api/memory/items", response_model=list[MemoryItemResponse])
async def memory_items(kind: MemoryKind | None = None, limit: int = 100) -> list[dict]:
    return memory_service.list_items(kind=kind, limit=limit)


@app.post("/api/memory/items", response_model=MemoryItemResponse)
async def create_memory_item(request: MemoryItemCreate, background_tasks: BackgroundTasks) -> dict:
    try:
        item = memory_service.create_item(
            kind=request.kind,
            key=request.key,
            value=request.value,
            confidence=request.confidence,
            source=request.source,
            source_id=request.source_id,
            overwrite=False,
        )
    except MemoryConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    background_tasks.add_task(_sync_memory_index, item["id"])
    return item


@app.patch("/api/memory/items/{item_id}", response_model=MemoryItemResponse)
async def update_memory_item(
    item_id: int, request: MemoryItemUpdate, background_tasks: BackgroundTasks,
) -> dict:
    try:
        item = memory_service.update_item(
            item_id,
            kind=request.kind,
            key=request.key,
            value=request.value,
            confidence=request.confidence,
            source=request.source,
            source_id=request.source_id,
        )
    except MemoryConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if item is None:
        raise HTTPException(status_code=404, detail="Recuerdo no encontrado.")
    background_tasks.add_task(_sync_memory_index, item["id"])
    return item


@app.delete("/api/memory/items/{item_id}")
async def delete_memory_item(item_id: int, background_tasks: BackgroundTasks) -> dict[str, bool]:
    deleted = memory_service.delete_item(item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Recuerdo no encontrado.")
    background_tasks.add_task(_sync_memory_index, item_id)
    return {"deleted": True}


@app.get("/api/profile", response_model=ProfileResponse)
async def profile() -> dict:
    return profile_service.get_profile()


@app.put("/api/profile", response_model=ProfileResponse)
async def update_profile(request: ProfileUpdate) -> dict:
    return profile_service.update_profile(request.model_dump(exclude_unset=True))


@app.get("/api/wardrobe/items", response_model=list[WardrobeItemResponse])
async def wardrobe_items(
    category: str | None = None,
    q: str | None = None,
    limit: int = 100,
) -> list[dict]:
    return wardrobe_service.list_items(category=category, query=q, limit=max(1, min(limit, 300)))


@app.post("/api/wardrobe/items", response_model=WardrobeItemResponse)
async def create_wardrobe_item(request: WardrobeItemCreate) -> dict:
    try:
        return wardrobe_service.create_item(**request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.patch("/api/wardrobe/items/{item_id}", response_model=WardrobeItemResponse)
async def update_wardrobe_item(item_id: int, request: WardrobeItemUpdate) -> dict:
    try:
        item = wardrobe_service.update_item(item_id, **request.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Prenda no encontrada.")
    return item


@app.delete("/api/wardrobe/items/{item_id}")
async def delete_wardrobe_item(item_id: int) -> dict[str, bool]:
    if not wardrobe_service.delete_item(item_id):
        raise HTTPException(status_code=404, detail="Prenda no encontrada.")
    return {"deleted": True}


@app.get("/api/wardrobe/images", response_model=list[WardrobeImageResponse])
async def wardrobe_images(item_id: int | None = None, limit: int = 200) -> list[dict]:
    return media_service.list_images(item_id=item_id, limit=max(1, min(limit, 300)))


@app.post("/api/wardrobe/images", response_model=WardrobeImageResponse)
async def upload_wardrobe_image(request: WardrobeImageUpload) -> dict:
    try:
        return media_service.upload_image(**request.model_dump())
    except MediaError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.patch("/api/wardrobe/images/{image_id}", response_model=WardrobeImageResponse)
async def update_wardrobe_image(image_id: int, request: WardrobeImageUpdate) -> dict:
    values = request.model_dump(exclude_unset=True)
    item_id = values.get("item_id")
    if item_id is not None and not db.get_wardrobe_item(int(item_id)):
        raise HTTPException(status_code=404, detail="Prenda no encontrada.")

    image = db.update_wardrobe_image(image_id, **values)
    if image is None:
        raise HTTPException(status_code=404, detail="Imagen no encontrada.")
    return media_service.image_response(image)


@app.delete("/api/wardrobe/images/{image_id}")
async def delete_wardrobe_image(image_id: int) -> dict[str, bool]:
    if not media_service.delete_image(image_id):
        raise HTTPException(status_code=404, detail="Imagen no encontrada.")
    return {"deleted": True}


@app.post("/api/vision/analyze", response_model=VisionAnalyzeResponse)
async def analyze_vision_image(request: VisionAnalyzeRequest) -> VisionAnalyzeResponse:
    image = db.get_wardrobe_image(request.image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Imagen no encontrada.")

    try:
        image_path = media_service.image_path(image)
        result = await vision_service.analyze_image(
            image_path=image_path,
            mime_type=image.get("mime_type") or "image/jpeg",
            prompt=request.prompt,
            provider=request.provider,
            model=request.model,
        )
    except MediaError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except VisionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    updated_image = db.update_wardrobe_image(request.image_id, analysis=result.analysis) or image
    memory_item = None
    if request.save_memory:
        memory_item = memory_service.create_item(
            kind="media_memory",
            key=f"media.images.{request.image_id}.analysis",
            value=_media_memory_value(updated_image, result.analysis),
            confidence=0.76,
            source="media",
            source_id=str(request.image_id),
        )
        await _try_semantic_upsert(memory_item)

    return VisionAnalyzeResponse(
        image=media_service.image_response(updated_image),
        provider=result.provider,
        model=result.model,
        analysis=result.analysis,
        memory_item=memory_item,
    )


@app.post("/api/wardrobe/images/{image_id}/extract", response_model=WardrobeImageExtractResponse)
async def extract_wardrobe_image(image_id: int, request: WardrobeImageExtractRequest) -> WardrobeImageExtractResponse:
    image = db.get_wardrobe_image(image_id)
    if not image:
        raise HTTPException(status_code=404, detail="Imagen no encontrada.")

    try:
        result = await vision_service.analyze_image(
            image_path=media_service.image_path(image),
            mime_type=image.get("mime_type") or "image/jpeg",
            prompt=style_service.extraction_prompt(request.prompt),
            provider=request.provider,
            model=request.model,
        )
    except MediaError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except VisionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    updated_image = db.update_wardrobe_image(image_id, analysis=result.analysis) or image
    draft = style_service.wardrobe_draft_from_analysis(result.analysis, image=updated_image)
    return WardrobeImageExtractResponse(
        image=media_service.image_response(updated_image),
        provider=result.provider,
        model=result.model,
        draft=draft,
        raw_analysis=result.analysis,
    )


@app.post("/api/vision/compare", response_model=VisionCompareResponse)
async def compare_vision_images(request: VisionCompareRequest) -> VisionCompareResponse:
    image_ids = list(dict.fromkeys(request.image_ids))
    if len(image_ids) < 2:
        raise HTTPException(status_code=400, detail="Selecciona al menos dos imagenes distintas.")

    images: list[dict] = []
    missing: list[int] = []
    for image_id in image_ids:
        image = db.get_wardrobe_image(image_id)
        if image:
            images.append(image)
        else:
            missing.append(image_id)
    if missing:
        raise HTTPException(status_code=404, detail=f"Imagenes no encontradas: {missing}")

    try:
        vision_inputs = [
            {
                "path": media_service.image_path(image),
                "mime_type": image.get("mime_type") or "image/jpeg",
                "label": _image_label(image),
            }
            for image in images
        ]
        result = await vision_service.compare_images(
            images=vision_inputs,
            prompt=request.prompt,
            provider=request.provider,
            model=request.model,
        )
    except MediaError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except VisionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    memory_item = None
    if request.save_memory:
        memory_item = memory_service.create_item(
            kind="media_memory",
            key=f"media.images.compare.{'.'.join(str(image_id) for image_id in image_ids)}",
            value=_comparison_memory_value(images, result.analysis),
            confidence=0.72,
            source="media_compare",
            source_id=",".join(str(image_id) for image_id in image_ids),
        )
        await _try_semantic_upsert(memory_item)

    return VisionCompareResponse(
        images=[media_service.image_response(image) for image in images],
        provider=result.provider,
        model=result.model,
        analysis=result.analysis,
        memory_item=memory_item,
    )


@app.post("/api/web/search", response_model=WebSearchResponse)
async def web_search(request: WebSearchRequest) -> WebSearchResponse:
    try:
        result = await web_search_service.search(
            request.query,
            provider=request.provider,
            limit=request.limit,
        )
    except WebSearchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _web_search_response(result)


@app.post("/api/style/research", response_model=StyleResearchResponse)
async def style_research(request: StyleResearchRequest) -> StyleResearchResponse:
    try:
        result = await style_service.research_brief(
            query=request.query,
            search_provider=request.search_provider,
            search_limit=request.search_limit,
            provider=request.provider,
            model=request.model,
        )
    except WebSearchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return StyleResearchResponse(
        query=result.query,
        brief=result.brief,
        provider=result.provider,
        model=result.model,
        search=_web_search_response(result.search),
    )


@app.post("/api/style/outfit-plan", response_model=OutfitPlanResponse)
async def style_outfit_plan(request: OutfitPlanRequest) -> OutfitPlanResponse:
    try:
        result = await style_service.outfit_plan(
            prompt=request.prompt,
            web_query=request.web_query,
            search_provider=request.search_provider,
            search_limit=request.search_limit,
            provider=request.provider,
            model=request.model,
        )
    except WebSearchError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return OutfitPlanResponse(
        prompt=result.prompt,
        plan=result.plan,
        provider=result.provider,
        model=result.model,
        search=_web_search_response(result.search) if result.search else None,
    )


@app.get("/api/context", response_model=ContextPreviewResponse)
async def context_preview(session_id: str | None = None, content: str = "") -> ContextPreviewResponse:
    if session_id and not db.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Sesion no encontrada.")
    context = await orchestrator.build_context(session_id=session_id, content=content)
    return ContextPreviewResponse(
        intent=context.intent.name,
        intent_reasons=context.intent.reasons,
        system_context=context.system_context,
        memory_items=context.memory_items,
        semantic_items=context.semantic_items,
        messages=context.messages,
    )


@app.get("/api/projects", response_model=list[MemoryItemResponse])
async def projects(limit: int = 100) -> list[dict]:
    return memory_service.list_items(kind="project_model", limit=limit)


@app.post("/api/projects", response_model=MemoryItemResponse)
async def create_project(request: ProjectCreate) -> dict:
    value = json.dumps(
        {
            "name": request.name,
            "status": request.status,
            "next_actions": request.next_actions,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    item = memory_service.create_item(
        kind="project_model",
        key=f"projects.{request.name}",
        value=value,
        confidence=0.9,
        source="api",
    )
    await _try_semantic_upsert(item)
    return item


@app.get("/api/semantic/status", response_model=SemanticStatusResponse)
async def semantic_status() -> SemanticStatusResponse:
    status = await semantic_memory_service.status()
    return SemanticStatusResponse(**status.__dict__)


@app.post("/api/semantic/index", response_model=SemanticIndexResponse)
async def semantic_index(kind: MemoryKind | None = None, limit: int = 500) -> dict:
    try:
        return await semantic_memory_service.index_memory_items(kind=kind, limit=limit)
    except SemanticMemoryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/semantic/search", response_model=list[SemanticSearchResultResponse])
async def semantic_search(q: str, limit: int = 8) -> list[dict]:
    try:
        results = await semantic_memory_service.search(q, limit=limit)
    except SemanticMemoryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return [
        {
            "score": result.score,
            "memory_item": result.memory_item,
            "payload": result.payload,
        }
        for result in results
    ]


@app.get("/api/reflections/candidates", response_model=list[ReflectionCandidateResponse])
async def reflection_candidates(
    status: ReflectionCandidateStatus | None = None,
    session_id: str | None = None,
    limit: int = 100,
) -> list[dict]:
    if session_id and not db.session_exists(session_id):
        raise HTTPException(status_code=404, detail="Sesion no encontrada.")
    try:
        return reflection_service.list_candidates(status=status, session_id=session_id, limit=limit)
    except ReflectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/reflections/run", response_model=ReflectionRunResponse)
async def run_reflection(request: ReflectionRunRequest) -> ReflectionRunResponse:
    try:
        result = await reflection_service.reflect_session(
            session_id=request.session_id,
            provider=request.provider,
            model=request.model,
            limit=request.limit,
        )
    except ReflectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ReflectionRunResponse(
        candidates=result.candidates,
        skipped=result.skipped,
        provider=result.provider,
        model=result.model,
        source=result.source,
    )


@app.patch("/api/reflections/candidates/{candidate_id}", response_model=ReflectionCandidateResponse)
async def update_reflection_candidate(candidate_id: int, request: ReflectionCandidateUpdate) -> dict:
    try:
        return reflection_service.update_candidate(
            candidate_id,
            kind=request.kind,
            key=request.key,
            value=request.value,
            confidence=request.confidence,
            rationale=request.rationale,
            evidence=request.evidence,
        )
    except ReflectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/reflections/candidates/{candidate_id}/approve", response_model=ReflectionReviewResponse)
async def approve_reflection_candidate(candidate_id: int) -> ReflectionReviewResponse:
    try:
        result = reflection_service.approve_candidate(candidate_id)
    except ReflectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if result.memory_item:
        await _try_semantic_upsert(result.memory_item)
    return ReflectionReviewResponse(candidate=result.candidate, memory_item=result.memory_item)


@app.post("/api/reflections/candidates/{candidate_id}/reject", response_model=ReflectionCandidateResponse)
async def reject_reflection_candidate(candidate_id: int) -> dict:
    try:
        return reflection_service.reject_candidate(candidate_id)
    except ReflectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _media_memory_value(image: dict, analysis: str) -> str:
    parts = [f"Vision analysis for wardrobe image {image['id']}"]
    item_id = image.get("item_id")
    if item_id:
        item = db.get_wardrobe_item(int(item_id))
        if item:
            parts.append(f"linked_item={item['name']}")
            parts.append(f"category={item['category']}")
    if image.get("original_name"):
        parts.append(f"file={image['original_name']}")
    trimmed_analysis = analysis.strip()
    if len(trimmed_analysis) > 3600:
        trimmed_analysis = trimmed_analysis[:3600].rstrip() + "..."
    parts.append(f"analysis={trimmed_analysis}")
    return "; ".join(parts)


def _web_search_response(result) -> WebSearchResponse:
    return WebSearchResponse(
        query=result.query,
        provider=result.provider,
        results=[item.__dict__ for item in result.results],
    )


def _image_label(image: dict) -> str:
    item_id = image.get("item_id")
    if item_id:
        item = db.get_wardrobe_item(int(item_id))
        if item:
            return f"{item['name']} ({item['category']})"
    return str(image.get("original_name") or f"image {image['id']}")


def _comparison_memory_value(images: list[dict], analysis: str) -> str:
    labels = ", ".join(_image_label(image) for image in images)
    trimmed_analysis = analysis.strip()
    if len(trimmed_analysis) > 3600:
        trimmed_analysis = trimmed_analysis[:3600].rstrip() + "..."
    return f"Vision comparison for wardrobe images: {labels}; analysis={trimmed_analysis}"


async def _sync_memory_index(item_id: int) -> None:
    # Serialize updates and read the latest state so queued edits cannot restore stale memory.
    async with memory_index_lock:
        item = db.get_memory_item(item_id)
        if item is None:
            await _try_semantic_delete(item_id)
        else:
            await _try_semantic_upsert(item)


async def _try_semantic_upsert(item: dict) -> None:
    try:
        await semantic_memory_service.upsert_memory_item(item)
    except SemanticMemoryError:
        return


async def _try_semantic_delete(item_id: int) -> None:
    try:
        await semantic_memory_service.delete_memory_item(item_id)
    except SemanticMemoryError:
        return


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            payload = await websocket.receive_json()
            try:
                request = ChatRequest(**payload)
            except ValidationError as exc:
                await websocket.send_json({"type": "error", "detail": exc.errors()})
                continue

            await websocket.send_json({"type": "status", "status": "processing"})
            try:
                async for event in orchestrator.stream_chat(
                    request.content,
                    session_id=request.session_id,
                    input_mode=request.input_mode,
                    output_mode=request.output_mode,
                    provider=request.provider,
                    model=request.model,
                ):
                    if event.type == "turn_started":
                        await websocket.send_json(
                            {
                                "type": "turn_started",
                                "session_id": event.session_id,
                                "user_message_id": event.user_message_id,
                                "input_mode": event.input_mode,
                                "output_mode": event.output_mode,
                                "provider": event.provider,
                                "model": event.model,
                            }
                        )
                    elif event.type == "tool_status":
                        await websocket.send_json(
                            {
                                "type": "tool_status",
                                "session_id": event.session_id,
                                "status": event.status,
                            }
                        )
                    elif event.type == "tool_result":
                        await websocket.send_json(
                            {
                                "type": "tool_result",
                                "session_id": event.session_id,
                                "name": event.tool_name,
                                "status": event.tool_status,
                                "content": event.content,
                                "payload": event.tool_payload or {},
                            }
                        )
                    elif event.type == "assistant_chunk":
                        await websocket.send_json(
                            {
                                "type": "assistant_chunk",
                                "session_id": event.session_id,
                                "delta": event.delta,
                                "provider": event.provider,
                                "model": event.model,
                            }
                        )
                    elif event.type == "assistant_message":
                        await websocket.send_json(
                            {
                                "type": "assistant_message",
                                "final": True,
                                "data": {
                                    "session_id": event.session_id,
                                    "user_message_id": event.user_message_id,
                                    "assistant_message_id": event.assistant_message_id,
                                    "content": event.content,
                                    "input_mode": event.input_mode,
                                    "output_mode": event.output_mode,
                                    "provider": event.provider,
                                    "model": event.model,
                                    "tokens_used": event.tokens_used,
                                },
                            }
                        )
            except (ValueError, LLMError) as exc:
                await websocket.send_json({"type": "error", "detail": str(exc)})
                continue
    except WebSocketDisconnect:
        return


def _voice_label(voice) -> str:
    return f"{voice.name} ({voice.culture})" if voice.culture else voice.name


def _tts_status_payload(status) -> dict:
    return {
        "name": status.name,
        "label": status.label,
        "available": status.available,
        "default_voice": status.default_voice,
        "voices": [
            {
                "id": voice.id,
                "label": _voice_label(voice),
                "culture": voice.culture,
            }
            for voice in status.voices
        ],
        "requires_api_key": status.requires_api_key,
        "detail": status.detail,
    }


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="Servidor API local de Mina Assistant.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Reinicia automaticamente el servidor al editar archivos.",
    )
    args = parser.parse_args()

    print(f"Mina Assistant API en http://{args.host}:{args.port}")
    print("Deja esta terminal abierta. Presiona Ctrl+C para detener.")
    app_target = "mina_assistant.app.main:app" if args.reload else app
    uvicorn.run(app_target, host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
