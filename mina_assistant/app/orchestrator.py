from __future__ import annotations

import re
from dataclasses import dataclass
from typing import AsyncIterator

from mina_assistant.app.chat_tools import ChatToolContext, ChatToolService
from mina_assistant.app.config import Settings
from mina_assistant.app.context import ContextBuilder, ContextPackage
from mina_assistant.app.db import SQLiteStore
from mina_assistant.app.intent import IntentClassifier
from mina_assistant.app.llm import LLMError, LLMResponse, LLMService
from mina_assistant.app.memory import MemoryService
from mina_assistant.app.semantic import SemanticMemoryError, SemanticMemoryService


@dataclass(frozen=True)
class TurnResult:
    session_id: str
    user_message_id: int
    assistant_message_id: int
    content: str
    input_mode: str
    output_mode: str
    model: str
    provider: str
    tokens_used: int | None


@dataclass(frozen=True)
class StreamEvent:
    type: str
    session_id: str
    user_message_id: int
    delta: str | None = None
    content: str | None = None
    assistant_message_id: int | None = None
    input_mode: str = "text"
    output_mode: str = "text"
    model: str | None = None
    provider: str | None = None
    tokens_used: int | None = None
    status: str | None = None
    tool_name: str | None = None
    tool_status: str | None = None
    tool_payload: dict | None = None


class AssistantOrchestrator:
    def __init__(
        self,
        settings: Settings,
        db: SQLiteStore,
        llm: LLMService,
        *,
        memory: MemoryService | None = None,
        context_builder: ContextBuilder | None = None,
        semantic_memory: SemanticMemoryService | None = None,
        chat_tools: ChatToolService | None = None,
    ):
        self.settings = settings
        self.db = db
        self.llm = llm
        self.memory = memory or MemoryService(db)
        self.semantic_memory = semantic_memory
        self.chat_tools = chat_tools
        self.context_builder = context_builder or ContextBuilder(
            settings=settings,
            db=db,
            memory=self.memory,
            intent_classifier=IntentClassifier(),
        )

    async def chat(
        self,
        content: str,
        *,
        session_id: str | None = None,
        input_mode: str = "text",
        output_mode: str = "text",
        provider: str | None = None,
        model: str | None = None,
    ) -> TurnResult:
        normalized_content = _normalize_user_text(content)
        title = _session_title(normalized_content)
        active_session_id = self.db.ensure_session(session_id, title=title)

        user_message_id = self.db.add_message(
            active_session_id,
            "user",
            normalized_content,
        )
        captured = self.memory.capture_from_user_message(
            session_id=active_session_id,
            message_id=user_message_id,
            content=normalized_content,
        )
        if captured:
            await self._try_semantic_upsert(captured.item)

        applied_pending = await self._try_apply_pending_action(active_session_id, normalized_content)
        if applied_pending:
            assistant_message_id = self.db.add_message(
                active_session_id,
                "assistant",
                applied_pending,
                model=_provider_model(provider or self.llm.default_provider(), model or self.llm.default_model(provider)),
            )
            return TurnResult(
                session_id=active_session_id,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
                content=applied_pending,
                input_mode=input_mode,
                output_mode=output_mode,
                model=_provider_model(provider or self.llm.default_provider(), model or self.llm.default_model(provider)),
                provider=provider or self.llm.default_provider(),
                tokens_used=None,
            )

        tool_context = await self._prepare_tool_context(active_session_id, normalized_content)
        questionnaire_response = _questionnaire_response(tool_context)
        if questionnaire_response:
            stored_model = _provider_model(provider or self.llm.default_provider(), model or self.llm.default_model(provider))
            assistant_message_id = self.db.add_message(
                active_session_id,
                "assistant",
                questionnaire_response,
                model=stored_model,
            )
            self.memory.record_turn_event(
                session_id=active_session_id,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
                provider=provider or self.llm.default_provider(),
                model=stored_model,
            )
            return TurnResult(
                session_id=active_session_id,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
                content=questionnaire_response,
                input_mode=input_mode,
                output_mode=output_mode,
                model=stored_model,
                provider=provider or self.llm.default_provider(),
                tokens_used=None,
            )

        llm_messages = await self._build_messages(
            active_session_id,
            normalized_content,
            tool_context=tool_context,
        )
        response = await self.llm.chat(llm_messages, provider=provider, model=model)
        response_content = _ensure_confirmation_question(_sanitize_assistant_content(response.content), tool_context)
        tokens_used = _tokens_used(response)
        stored_model = _provider_model(response.provider, response.model)

        assistant_message_id = self.db.add_message(
            active_session_id,
            "assistant",
            response_content,
            tokens=tokens_used,
            model=stored_model,
        )
        self.memory.record_turn_event(
            session_id=active_session_id,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            provider=response.provider,
            model=stored_model,
        )
        await self._create_pending_action_from_turn(
            session_id=active_session_id,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            user_content=normalized_content,
            assistant_content=response_content,
            tool_context=tool_context,
        )

        return TurnResult(
            session_id=active_session_id,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            content=response_content,
            input_mode=input_mode,
            output_mode=output_mode,
            model=stored_model,
            provider=response.provider,
            tokens_used=tokens_used,
        )

    async def stream_chat(
        self,
        content: str,
        *,
        session_id: str | None = None,
        input_mode: str = "text",
        output_mode: str = "text",
        provider: str | None = None,
        model: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        normalized_content = _normalize_user_text(content)
        title = _session_title(normalized_content)
        active_session_id = self.db.ensure_session(session_id, title=title)

        user_message_id = self.db.add_message(
            active_session_id,
            "user",
            normalized_content,
        )
        captured = self.memory.capture_from_user_message(
            session_id=active_session_id,
            message_id=user_message_id,
            content=normalized_content,
        )
        if captured:
            await self._try_semantic_upsert(captured.item)

        applied_pending = await self._try_apply_pending_action(active_session_id, normalized_content)
        yield StreamEvent(
            type="turn_started",
            session_id=active_session_id,
            user_message_id=user_message_id,
            input_mode=input_mode,
            output_mode=output_mode,
            provider=provider or self.llm.default_provider(),
            model=model or self.llm.default_model(provider),
        )
        if applied_pending:
            stored_model = _provider_model(provider or self.llm.default_provider(), model or self.llm.default_model(provider))
            yield StreamEvent(
                type="tool_status",
                session_id=active_session_id,
                user_message_id=user_message_id,
                status="Guardando memoria confirmada",
            )
            yield StreamEvent(
                type="assistant_chunk",
                session_id=active_session_id,
                user_message_id=user_message_id,
                delta=applied_pending,
                input_mode=input_mode,
                output_mode=output_mode,
                provider=provider or self.llm.default_provider(),
                model=model or self.llm.default_model(provider),
            )
            assistant_message_id = self.db.add_message(
                active_session_id,
                "assistant",
                applied_pending,
                model=stored_model,
            )
            self.memory.record_turn_event(
                session_id=active_session_id,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
                provider=provider or self.llm.default_provider(),
                model=stored_model,
            )
            yield StreamEvent(
                type="assistant_message",
                session_id=active_session_id,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
                content=applied_pending,
                input_mode=input_mode,
                output_mode=output_mode,
                provider=provider or self.llm.default_provider(),
                model=stored_model,
                tokens_used=None,
            )
            return

        tool_plan = self.chat_tools.plan(normalized_content, session_id=active_session_id) if self.chat_tools else None
        if tool_plan and tool_plan.style_related:
            yield StreamEvent(
                type="tool_status",
                session_id=active_session_id,
                user_message_id=user_message_id,
                status="Consultando perfil y guardarropa",
            )
        if tool_plan and tool_plan.web_search:
            status_query = (
                self.chat_tools.search_status_query(normalized_content, session_id=active_session_id, kind="web")
                if self.chat_tools
                else _short_status_query(normalized_content)
            )
            yield StreamEvent(
                type="tool_status",
                session_id=active_session_id,
                user_message_id=user_message_id,
                status=f"Buscando referencias: {status_query}",
            )
        if tool_plan and tool_plan.product_search:
            status_query = (
                self.chat_tools.search_status_query(normalized_content, session_id=active_session_id, kind="product")
                if self.chat_tools
                else _short_status_query(normalized_content)
            )
            yield StreamEvent(
                type="tool_status",
                session_id=active_session_id,
                user_message_id=user_message_id,
                status=f"Buscando productos reales: {status_query}",
            )
        if tool_plan and tool_plan.price_search:
            status_query = (
                self.chat_tools.search_status_query(normalized_content, session_id=active_session_id, kind="price")
                if self.chat_tools
                else _short_status_query(normalized_content)
            )
            yield StreamEvent(
                type="tool_status",
                session_id=active_session_id,
                user_message_id=user_message_id,
                status=f"Buscando precios y disponibilidad: {status_query}",
            )
        if tool_plan and tool_plan.profile_questionnaire:
            yield StreamEvent(
                type="tool_status",
                session_id=active_session_id,
                user_message_id=user_message_id,
                status="Preparando cuestionario de perfil",
            )
        if tool_plan and tool_plan.shopping_questionnaire:
            yield StreamEvent(
                type="tool_status",
                session_id=active_session_id,
                user_message_id=user_message_id,
                status="Preparando selector interactivo de piezas",
            )

        tool_context = await self._prepare_tool_context(
            active_session_id,
            normalized_content,
            plan=tool_plan,
        )
        if tool_context and tool_context.results:
            for result in tool_context.results:
                yield StreamEvent(
                    type="tool_result",
                    session_id=active_session_id,
                    user_message_id=user_message_id,
                    tool_name=result.name,
                    tool_status=result.status,
                    content=result.content,
                    tool_payload=result.payload,
                )
        questionnaire_response = _questionnaire_response(tool_context)
        if questionnaire_response:
            provider_used = provider or self.llm.default_provider()
            model_used = model or self.llm.default_model(provider)
            stored_model = _provider_model(provider_used, model_used)
            yield StreamEvent(
                type="assistant_chunk",
                session_id=active_session_id,
                user_message_id=user_message_id,
                delta=questionnaire_response,
                input_mode=input_mode,
                output_mode=output_mode,
                provider=provider_used,
                model=model_used,
            )
            assistant_message_id = self.db.add_message(
                active_session_id,
                "assistant",
                questionnaire_response,
                model=stored_model,
            )
            self.memory.record_turn_event(
                session_id=active_session_id,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
                provider=provider_used,
                model=stored_model,
            )
            yield StreamEvent(
                type="assistant_message",
                session_id=active_session_id,
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
                content=questionnaire_response,
                input_mode=input_mode,
                output_mode=output_mode,
                provider=provider_used,
                model=stored_model,
                tokens_used=None,
            )
            return

        if tool_plan and tool_plan.outfit_plan:
            yield StreamEvent(
                type="tool_status",
                session_id=active_session_id,
                user_message_id=user_message_id,
                status="Armando plan con tu contexto",
            )

        chunks: list[str] = []
        provider_used = provider or self.llm.default_provider()
        model_used = model or self.llm.default_model(provider)
        prompt_eval_count: int | None = None
        eval_count: int | None = None

        llm_messages = await self._build_messages(
            active_session_id,
            normalized_content,
            tool_context=tool_context,
        )
        async for chunk in self.llm.chat_stream(llm_messages, provider=provider, model=model):
            provider_used = chunk.provider or provider_used
            model_used = chunk.model or model_used
            if chunk.prompt_eval_count is not None:
                prompt_eval_count = chunk.prompt_eval_count
            if chunk.eval_count is not None:
                eval_count = chunk.eval_count

            if chunk.content:
                chunks.append(chunk.content)
                yield StreamEvent(
                    type="assistant_chunk",
                    session_id=active_session_id,
                    user_message_id=user_message_id,
                    delta=chunk.content,
                    input_mode=input_mode,
                    output_mode=output_mode,
                    provider=provider_used,
                    model=model_used,
                )

        response_content = _sanitize_assistant_content("".join(chunks).strip())
        if not response_content:
            raise LLMError("The LLM provider returned an empty response.")
        final_content = _ensure_confirmation_question(response_content, tool_context)
        suffix = final_content[len(response_content) :]
        if suffix:
            yield StreamEvent(
                type="assistant_chunk",
                session_id=active_session_id,
                user_message_id=user_message_id,
                delta=suffix,
                input_mode=input_mode,
                output_mode=output_mode,
                provider=provider_used,
                model=model_used,
            )
        response_content = final_content

        response = LLMResponse(
            content=response_content,
            model=model_used,
            provider=provider_used,
            prompt_eval_count=prompt_eval_count,
            eval_count=eval_count,
        )
        tokens_used = _tokens_used(response)
        stored_model = _provider_model(provider_used, model_used)

        assistant_message_id = self.db.add_message(
            active_session_id,
            "assistant",
            response_content,
            tokens=tokens_used,
            model=stored_model,
        )
        self.memory.record_turn_event(
            session_id=active_session_id,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            provider=provider_used,
            model=stored_model,
        )
        await self._create_pending_action_from_turn(
            session_id=active_session_id,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            user_content=normalized_content,
            assistant_content=response_content,
            tool_context=tool_context,
        )

        yield StreamEvent(
            type="assistant_message",
            session_id=active_session_id,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            content=response_content,
            input_mode=input_mode,
            output_mode=output_mode,
            provider=provider_used,
            model=stored_model,
            tokens_used=tokens_used,
        )

    async def build_context(self, session_id: str | None = None, content: str = "") -> ContextPackage:
        return await self.context_builder.build(session_id=session_id, content=content)

    async def _build_messages(
        self,
        session_id: str,
        content: str,
        *,
        tool_context: ChatToolContext | None = None,
    ) -> list[dict[str, str]]:
        messages = list((await self.build_context(session_id=session_id, content=content)).messages)
        tool_message = tool_context.system_message() if tool_context else None
        if tool_message and messages and messages[0]["role"] == "system":
            messages[0] = {
                "role": "system",
                "content": f"{messages[0]['content']}\n\n{tool_message}",
            }
        elif tool_message:
            messages.insert(0, {"role": "system", "content": tool_message})
        return messages

    async def _prepare_tool_context(self, session_id: str, content: str, *, plan=None) -> ChatToolContext | None:
        if not self.chat_tools:
            return None
        tool_context = await self.chat_tools.prepare(content, plan=plan, session_id=session_id)
        if tool_context.results:
            self.db.add_assistant_event(
                session_id=session_id,
                event_type="chat_tool_context",
                payload=tool_context.event_payload(),
            )
        return tool_context

    async def _try_semantic_upsert(self, item: dict) -> None:
        if not self.semantic_memory:
            return
        try:
            await self.semantic_memory.upsert_memory_item(item)
        except SemanticMemoryError:
            return

    async def _try_apply_pending_action(self, session_id: str, content: str) -> str | None:
        if not _is_affirmative_confirmation(content):
            return None
        pending = self.db.latest_pending_action(session_id)
        if not pending:
            return None
        payload = pending.get("payload") or {}
        if pending.get("action_type") != "save_memory":
            self.db.resolve_pending_action(int(pending["id"]), status="cancelled")
            return "No pude aplicar esa accion pendiente porque aun no esta soportada."

        item = self.memory.create_item(
            kind=str(payload.get("memory_kind") or "style_reference"),
            key=str(payload.get("memory_key") or "chat.saved_reference"),
            value=str(payload.get("memory_value") or ""),
            confidence=float(payload.get("confidence") or 0.75),
            source="chat_confirmation",
            source_id=str(pending["id"]),
        )
        await self._try_semantic_upsert(item)
        self.db.resolve_pending_action(int(pending["id"]), status="applied")
        self.db.add_assistant_event(
            session_id=session_id,
            event_type="pending_action_applied",
            payload={"pending_action_id": pending["id"], "memory_item_id": item["id"]},
        )
        return f"Listo, lo guarde en memoria: {item['value']}"

    async def _create_pending_action_from_turn(
        self,
        *,
        session_id: str,
        user_message_id: int,
        assistant_message_id: int,
        user_content: str,
        assistant_content: str,
        tool_context: ChatToolContext | None,
    ) -> None:
        action = _pending_action_from_tool_context(
            user_content=user_content,
            assistant_content=assistant_content,
            tool_context=tool_context,
        )
        if not action:
            return
        payload = {
            **action["payload"],
            "user_message_id": user_message_id,
            "assistant_message_id": assistant_message_id,
        }
        pending = self.db.create_pending_action(
            session_id=session_id,
            action_type=action["action_type"],
            payload=payload,
        )
        self.db.add_assistant_event(
            session_id=session_id,
            event_type="pending_action_created",
            payload={"pending_action_id": pending["id"], "action_type": pending["action_type"]},
        )


def _normalize_user_text(content: str) -> str:
    normalized = re.sub(r"\s+", " ", content).strip()
    if not normalized:
        raise ValueError("El mensaje no puede estar vacio.")
    return normalized


def _session_title(content: str) -> str:
    title = content[:60].strip()
    if len(content) > 60:
        title = f"{title}..."
    return title


def _tokens_used(response: LLMResponse) -> int | None:
    values = [response.prompt_eval_count, response.eval_count]
    if all(value is None for value in values):
        return None
    return sum(value or 0 for value in values)


def _provider_model(provider: str, model: str) -> str:
    return f"{provider}/{model}"


def _ensure_confirmation_question(content: str, tool_context: ChatToolContext | None) -> str:
    if not tool_context or not tool_context.results:
        return content
    normalized = content.lower()
    if re.search(r"(quieres|te gustaria|deseas|guardo|guardar|save|should i save).*\?", normalized):
        return content

    names = {result.name for result in tool_context.results}
    if "preference_candidate" in names:
        question = "Quieres que guarde esta preferencia para recordarla entre sesiones?"
    elif "build_outfit" in names or "outfit_planner_guidance" in names:
        question = "Quieres que guarde este plan como referencia para futuros outfits?"
    elif "get_prices" in names:
        question = "Quieres que guarde estos precios o productos como referencia para futuras compras?"
    elif "product_search" in names or "web_search" in names:
        question = "Quieres que guarde esto como referencia para recordarlo despues?"
    elif "wardrobe_context" in names:
        question = "Quieres que actualice alguna preferencia o dato de tu guardarropa con esto?"
    else:
        question = "Quieres que guarde algo de esto para futuras conversaciones?"
    return f"{content.rstrip()}\n\n{question}"


def _questionnaire_response(tool_context: ChatToolContext | None) -> str | None:
    if not tool_context:
        return None
    names = {result.name for result in tool_context.results}
    if "shopping_questionnaire" in names:
        return (
            "Te dejo un selector interactivo para elegir piezas, presupuesto y prioridad. "
            "Cuando lo envies, armo el plan y busco productos reales con queries especificas."
        )
    if "style_profile_questionnaire" not in names:
        return None
    return (
        "Te dejo un cuestionario interactivo para armar tu perfil de estilo. "
        "Complétalo cuando quieras; si prefieres saltarlo, seguimos conversando normal."
    )


def _sanitize_assistant_content(content: str) -> str:
    cleaned = content.strip()
    if not cleaned:
        return cleaned

    weak_patterns = [
        r"^\s*como\s+soy\s+una\s+asistente\s+sin\s+sentido\s+del\s+olfato,\s*",
        r"^\s*como\s+asistente\s+(?:de\s+ia\s+)?(?:no\s+tengo|sin)\s+[^.?!]*(?:olfato|gusto|sentidos)[.?!]\s*",
        r"^\s*como\s+(?:ia|modelo\s+de\s+lenguaje)[^.?!]*[.?!]\s*",
        r"\bno\s+puedo\s+(?:oler|probar|experimentar)\s+(?:las|los|perfumes|fragancias)[^.?!]*[.?!]\s*",
        r"\bno\s+puedo\s+(?:olerlas|olerlos|probarlas|probarlos|experimentarlas|experimentarlos)[^.?!]*[.?!]\s*",
        r"\bno\s+tengo\s+(?:olfato|gusto|sentidos|experiencia\s+personal)[^.?!]*[.?!]\s*",
        r"\bas\s+an\s+ai(?:\s+language\s+model)?[^.?!]*[.?!]\s*",
    ]
    for pattern in weak_patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    return cleaned.lstrip(" \n-:;")


def _short_status_query(content: str, *, limit: int = 58) -> str:
    cleaned = re.sub(r"\s+", " ", content).strip(" ?.,;:")
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _is_affirmative_confirmation(content: str) -> bool:
    normalized = content.strip().lower()
    normalized = normalized.replace("í", "i").replace("á", "a").replace("é", "e").replace("ó", "o").replace("ú", "u")
    return bool(
        re.search(
            r"^(si|sii|dale|ok|okay|perfecto|guardalo|guardar|guarda|yes|save it|do it|hazlo)\b",
            normalized,
        )
    )


def _pending_action_from_tool_context(
    *,
    user_content: str,
    assistant_content: str,
    tool_context: ChatToolContext | None,
) -> dict | None:
    if not tool_context:
        return None
    by_name = {result.name: result for result in tool_context.results}
    preference = by_name.get("preference_candidate")
    if preference:
        payload = preference.payload
        return {
            "action_type": "save_memory",
            "payload": {
                "memory_kind": payload.get("memory_kind") or "fashion_preference",
                "memory_key": payload.get("memory_key") or f"fashion.preferences.{_memory_key(user_content)}",
                "memory_value": payload.get("memory_value") or user_content,
                "confidence": payload.get("confidence") or 0.74,
            },
        }

    if "build_outfit" in by_name or "outfit_planner_guidance" in by_name:
        value = f"Outfit plan reference. Request: {user_content}. Plan: {_compact(assistant_content, 1600)}"
        return {
            "action_type": "save_memory",
            "payload": {
                "memory_kind": "style_reference",
                "memory_key": f"fashion.outfit_plans.{_memory_key(user_content)}",
                "memory_value": value,
                "confidence": 0.78,
            },
        }

    product = by_name.get("product_search") or by_name.get("get_prices") or by_name.get("web_search")
    if product:
        payload = product.payload
        query = str(payload.get("query") or user_content)
        value = f"Style/product reference researched: {query}. Summary: {_compact(assistant_content, 1200)}"
        return {
            "action_type": "save_memory",
            "payload": {
                "memory_kind": "style_reference",
                "memory_key": f"fashion.references.{_memory_key(query)}",
                "memory_value": value,
                "confidence": 0.68,
            },
        }
    return None


def _memory_key(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", ".", value.strip().lower())
    cleaned = re.sub(r"\.+", ".", cleaned).strip(".")
    return (cleaned or "reference")[:90]


def _compact(value: str, limit: int) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."
