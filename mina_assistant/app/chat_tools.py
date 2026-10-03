from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from mina_assistant.app.db import SQLiteStore
from mina_assistant.app.profile import PERSONALIZATION_POLICY, ProfileService
from mina_assistant.app.web_search import WebImageResult, WebSearchError, WebSearchResponse, WebSearchService


@dataclass(frozen=True)
class ChatToolPlan:
    style_related: bool = False
    profile_questionnaire: bool = False
    shopping_questionnaire: bool = False
    web_search: bool = False
    product_search: bool = False
    price_search: bool = False
    outfit_plan: bool = False
    preference_candidate: bool = False


@dataclass(frozen=True)
class ChatToolResult:
    name: str
    status: str
    content: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChatToolContext:
    results: list[ChatToolResult]

    def system_message(self) -> str | None:
        if not self.results:
            return None
        blocks = [
            "Internal Mina tool context.",
            PERSONALIZATION_POLICY.strip(),
            "Use this context naturally from chat. Do not mention internal tool names unless the user asks.",
            "When web sources are present, cite them with [1], [2], etc.",
            "For product_search and get_prices, recommend only products present in the tool results.",
            "Never invent a price, store, or availability. If it is not visible, say it was not visible in the search result.",
            "Search tool rule: the user's command is not the search query. For fashion shopping, use concrete terms: item type, aesthetic, color, fit, material, Chile/store, and price.",
            "For outfit planning, combine owned wardrobe items first, then suggest missing products only when useful.",
            "For shopping_questionnaire, the frontend renders the interactive card. Do not rewrite the questions or options as prose.",
            "For perfume/beauty/product recommendations, answer as a curator: group options by mood or use case, pick top options, and explain why.",
            "If the user asks which option you like more, choose one based on notes, versatility, occasion, sources, and the user's saved preferences.",
            "Never say you lack smell, taste, a body, personal experience, feelings, or senses. Do not mention being an AI/model.",
            "Avoid raw Markdown tables unless they are compact and well formed. Prefer sections with bullets and source citations.",
            "After using web, wardrobe, profile, or planner context, end with one concise confirmation question about the next useful action.",
            "Examples: ask if the user wants to save the perfume as a wardrobe/reference item, save a preference, or save the outfit plan.",
            "Never change stable memory, wardrobe, or plans without explicit confirmation.",
            "If the user wants a plan, make the plan in chat and include concrete next steps.",
        ]
        for result in self.results:
            blocks.append(f"\n[{result.name} | {result.status}]\n{result.content}")
        return "\n".join(blocks).strip()

    def event_payload(self) -> dict[str, Any]:
        return {
            "tools": [
                {
                    "name": result.name,
                    "status": result.status,
                    "payload": result.payload,
                }
                for result in self.results
            ]
        }


class ChatToolService:
    def __init__(self, *, db: SQLiteStore, profile: ProfileService, web_search: WebSearchService):
        self.db = db
        self.profile = profile
        self.web_search = web_search

    def plan(self, content: str, *, session_id: str | None = None) -> ChatToolPlan:
        conversation_context = self._conversation_context(session_id)
        contextual_style = _is_contextual_style_followup(content) and _is_style_related(conversation_context)
        style_related = _is_style_related(content) or contextual_style
        shopping_questionnaire = _should_offer_shopping_questionnaire(content)
        return ChatToolPlan(
            style_related=style_related,
            profile_questionnaire=(
                _should_offer_style_questionnaire(content, self.profile.get_profile())
                and not shopping_questionnaire
            ),
            shopping_questionnaire=shopping_questionnaire,
            web_search=_should_search_web(content) and not shopping_questionnaire,
            product_search=(
                _should_product_search(content)
                or (style_related and _should_search_web(content) and _is_shopping_or_plan_followup(content))
            )
            and not shopping_questionnaire,
            price_search=_should_price_search(content) and not shopping_questionnaire,
            outfit_plan=_should_plan_outfit(content) and not shopping_questionnaire,
            preference_candidate=_should_suggest_preference(content),
        )

    async def prepare(
        self,
        content: str,
        *,
        plan: ChatToolPlan | None = None,
        session_id: str | None = None,
    ) -> ChatToolContext:
        text = content.strip()
        if not text:
            return ChatToolContext(results=[])

        conversation_context = self._conversation_context(session_id)
        query_context = _query_context(text, conversation_context)
        active_plan = plan or self.plan(text, session_id=session_id)
        results: list[ChatToolResult] = []
        if active_plan.style_related:
            results.append(self._profile_result())
            results.append(self._wardrobe_result(text))

        if active_plan.profile_questionnaire:
            results.append(self._style_questionnaire_result())

        if active_plan.shopping_questionnaire:
            results.append(self._shopping_questionnaire_result(query_context))

        if active_plan.web_search:
            results.append(await self._web_result(text, context=query_context))

        if active_plan.product_search:
            results.append(await self._product_result(text, context=query_context))

        if active_plan.price_search:
            results.append(await self._price_result(text, context=query_context))

        if active_plan.outfit_plan:
            results.append(self._build_outfit_result(text))

        if active_plan.preference_candidate:
            candidate = _preference_candidate(text)
            if candidate:
                results.append(candidate)

        return ChatToolContext(results=[result for result in results if result.content.strip()])

    def search_status_query(self, content: str, *, session_id: str | None = None, kind: str = "web") -> str:
        context = _query_context(content, self._conversation_context(session_id))
        if kind == "product":
            return _short_query(_product_query(content, context=context))
        if kind == "price":
            return _short_query(_price_query(content, context=context))
        return _short_query(_web_query(content, context=context))

    def _conversation_context(self, session_id: str | None) -> str:
        if not session_id:
            return ""
        try:
            rows = self.db.get_recent_messages(session_id, limit=10)
        except Exception:
            return ""
        lines: list[str] = []
        for row in rows:
            role = str(row.get("role") or "")
            if role not in {"user", "assistant"}:
                continue
            content = str(row.get("content") or "").strip()
            if content:
                lines.append(f"{role}: {_compact(content, 700)}")
        return "\n".join(lines)

    def _profile_result(self) -> ChatToolResult:
        profile = self.profile.get_profile()
        lines: list[str] = []
        labels = {
            "display_name": "name",
            "gender_identity": "style gender identity",
            "age_range": "age range",
            "city": "city/climate",
            "height": "height",
            "body_notes": "body notes",
            "size_tops": "top size",
            "size_bottoms": "bottom size",
            "size_shoes": "shoe size",
            "fit_preferences": "fit preferences",
            "favorite_colors": "favorite colors",
            "avoided_colors": "avoided colors",
            "style_keywords": "style keywords",
            "primary_occasion": "primary occasion",
            "style_focus": "style focus",
            "comfort_notes": "comfort",
            "budget_notes": "budget",
        }
        for key, label in labels.items():
            value = str(profile.get(key) or "").strip()
            if value:
                lines.append(f"- {label}: {value}")
        lines.append("\n" + self.profile.user_context_block())
        return ChatToolResult(
            name="profile_context",
            status="ready",
            content="\n".join(lines) if lines else "No confirmed profile details yet.",
            payload={"fields": [key for key, value in profile.items() if value and key != "updated_at"]},
        )

    def _style_questionnaire_result(self) -> ChatToolResult:
        profile = self.profile.get_profile()
        missing = [
            key
            for key in ("gender_identity", "age_range", "style_keywords", "primary_occasion", "style_focus")
            if not str(profile.get(key) or "").strip()
        ]
        return ChatToolResult(
            name="style_profile_questionnaire",
            status="needs_input",
            content=(
                "Offer the interactive style profile card. Do not repeat every question in prose. "
                "Briefly explain that answering it lets Mina personalize outfits, makeup, skincare, perfume, "
                "shopping, image analysis, and web research. If the user skips it, continue normally."
            ),
            payload={
                "title": "Tu perfil de estilo",
                "intro": "Completa esto una vez para que Mina personalice mejor moda, maquillaje, perfumes y compras.",
                "missing_fields": missing,
                "questions": [
                    {
                        "id": "gender_identity",
                        "profile_field": "gender_identity",
                        "label": "Genero o identidad para recomendaciones de estilo",
                        "type": "single",
                        "options": [
                            {"label": "Mujer", "value": "Mujer"},
                            {"label": "Hombre", "value": "Hombre"},
                            {"label": "No binario", "value": "No binario"},
                            {"label": "Otro / prefiero decirlo yo", "value": "Otro"},
                        ],
                    },
                    {
                        "id": "age_range",
                        "profile_field": "age_range",
                        "label": "Rango de edad",
                        "type": "single",
                        "options": [
                            {"label": "18-24", "value": "18-24"},
                            {"label": "25-34", "value": "25-34"},
                            {"label": "35-45", "value": "35-45"},
                            {"label": "45+", "value": "45+"},
                        ],
                    },
                    {
                        "id": "style_keywords",
                        "profile_field": "style_keywords",
                        "label": "Estetica o vibe principal",
                        "type": "single",
                        "options": [
                            {"label": "Casual moderno", "value": "casual moderno", "description": "comodo pero arreglado"},
                            {"label": "Minimalista", "value": "minimalista", "description": "limpio, neutro, sin excesos"},
                            {"label": "Profesional", "value": "profesional", "description": "ejecutivo, smart casual"},
                            {"label": "Romantica", "value": "romantica", "description": "flores, colores suaves"},
                            {"label": "Urbano / streetwear", "value": "urbano streetwear", "description": "sneakers, marcas, actitud"},
                            {"label": "No se aun", "value": "por definir", "description": "Mina ayudara a definirlo"},
                        ],
                    },
                    {
                        "id": "primary_occasion",
                        "profile_field": "primary_occasion",
                        "label": "Ocasion principal",
                        "type": "single",
                        "options": [
                            {"label": "Diario", "value": "diario"},
                            {"label": "Trabajo", "value": "trabajo"},
                            {"label": "Salidas / social", "value": "salidas social"},
                            {"label": "Eventos", "value": "eventos"},
                            {"label": "Deporte / outdoor", "value": "deporte outdoor"},
                        ],
                    },
                    {
                        "id": "style_focus",
                        "profile_field": "style_focus",
                        "label": "Que quieres trabajar primero",
                        "type": "single",
                        "options": [
                            {"label": "Outfits y ropa", "value": "outfits y ropa", "description": "combinaciones y prendas"},
                            {"label": "Maquillaje", "value": "maquillaje", "description": "looks, tonos y tecnicas"},
                            {"label": "Skincare", "value": "skincare", "description": "rutina y productos"},
                            {"label": "Perfumes", "value": "perfumes", "description": "fragancias, notas y marcas"},
                            {"label": "Todo / look completo", "value": "todo look completo", "description": "de pies a cabeza"},
                        ],
                    },
                    {
                        "id": "extra_notes",
                        "profile_field": "comfort_notes",
                        "label": "Algo mas que quieras contarme",
                        "type": "text",
                        "placeholder": "Ej: piel grasa, colores favoritos, marcas, presupuesto, prendas que odias...",
                    },
                ],
            },
        )

    def _shopping_questionnaire_result(self, query_context: str) -> ChatToolResult:
        context_hint = _contextual_fashion_query(query_context, intent="product") or _product_query(
            "piezas clave de moda",
            context=query_context,
        )
        return ChatToolResult(
            name="shopping_questionnaire",
            status="needs_input",
            content=(
                "Render the interactive shopping/style selection card. Do not repeat the questions in prose. "
                "When submitted, use the selected answers to create a shopping plan and run product searches with specific queries."
            ),
            payload={
                "ui_schema": "shopping_questionnaire.v1",
                "title": "Selector de piezas",
                "intro": "Elige prioridades para que Mina arme el plan de compra y busque productos concretos.",
                "context_hint": context_hint,
                "submit_label": "Armar plan y buscar",
                "questions": [
                    {
                        "id": "occasion",
                        "label": "Uso principal",
                        "type": "single",
                        "options": [
                            {"label": "Dia casual-rock", "value": "dia casual rock", "description": "cafe, campus, ciudad"},
                            {"label": "Noche glam-punk", "value": "noche glam punk", "description": "club, concierto, cita"},
                            {"label": "Salida elegante", "value": "salida social elegante", "description": "cena, coctel, evento"},
                        ],
                    },
                    {
                        "id": "budget",
                        "label": "Presupuesto por pieza",
                        "type": "single",
                        "options": [
                            {"label": "Ajustado", "value": "hasta CLP 30000", "description": "basicos y ofertas"},
                            {"label": "Medio", "value": "CLP 30000 a 80000", "description": "mejor tela o calce"},
                            {"label": "Alto", "value": "sobre CLP 80000", "description": "calidad y marcas premium"},
                        ],
                    },
                    {
                        "id": "fit",
                        "label": "Silueta",
                        "type": "single",
                        "options": [
                            {"label": "Slim", "value": "slim recto", "description": "linea angosta y limpia"},
                            {"label": "Recta", "value": "recto estructurado", "description": "pulido sin apretar"},
                            {"label": "Oversize", "value": "oversize controlado", "description": "volumen con estructura"},
                        ],
                    },
                    {
                        "id": "pieces",
                        "label": "Piezas a buscar",
                        "type": "multi",
                        "options": [
                            {"label": "Pantalon sastre negro", "value": "pantalon sastre negro slim"},
                            {"label": "Camiseta basica blanca/gris", "value": "camiseta basica blanca gris algodon"},
                            {"label": "Botines Chelsea negros", "value": "botines Chelsea negros cuero"},
                            {"label": "Top saten negro", "value": "top saten negro cuello V"},
                            {"label": "Falda midi plisada negra", "value": "falda midi plisada negra"},
                            {"label": "Cinturon cuero hebilla", "value": "cinturon ancho cuero negro hebilla metalica"},
                        ],
                    },
                    {
                        "id": "stores",
                        "label": "Tiendas objetivo",
                        "type": "multi",
                        "options": [
                            {"label": "Zara Chile", "value": "Zara Chile"},
                            {"label": "Mango Chile", "value": "Mango Chile"},
                            {"label": "Falabella", "value": "Falabella"},
                            {"label": "Paris", "value": "Paris"},
                            {"label": "Mercado Libre", "value": "Mercado Libre Chile"},
                        ],
                    },
                    {
                        "id": "timeline",
                        "label": "Plazo",
                        "type": "single",
                        "options": [
                            {"label": "Urgente", "value": "menos de una semana"},
                            {"label": "Normal", "value": "una a tres semanas"},
                            {"label": "Flexible", "value": "mas de tres semanas"},
                        ],
                    },
                    {
                        "id": "notes",
                        "label": "Notas",
                        "type": "text",
                        "placeholder": "Tallas, marcas que evitar, materiales, ciudad o cualquier restriccion.",
                    },
                ],
            },
        )

    def _wardrobe_result(self, content: str) -> ChatToolResult:
        query = _wardrobe_query(content)
        items = self.db.list_wardrobe_items(query=query, limit=24)
        if not items and query:
            items = self.db.list_wardrobe_items(limit=24)
        if not items:
            return ChatToolResult(
                name="wardrobe_context",
                status="empty",
                content="No saved wardrobe items yet.",
                payload={"query": query, "count": 0},
            )

        lines: list[str] = []
        for item in items:
            parts = [
                str(item.get("name") or "Unnamed"),
                f"category={item.get('category') or 'unknown'}",
            ]
            for key in ("subcategory", "brand", "size_label", "fit", "material", "season"):
                if item.get(key):
                    parts.append(f"{key}={item[key]}")
            if item.get("colors"):
                parts.append(f"colors={', '.join(item['colors'])}")
            if item.get("occasions"):
                parts.append(f"occasions={', '.join(item['occasions'])}")
            if item.get("style_tags"):
                parts.append(f"tags={', '.join(item['style_tags'])}")
            if item.get("favorite"):
                parts.append("favorite=true")
            if item.get("notes"):
                parts.append(f"notes={_compact(str(item['notes']), 180)}")
            lines.append("- " + "; ".join(parts))

        return ChatToolResult(
            name="wardrobe_context",
            status="ready",
            content="\n".join(lines),
            payload={"query": query, "count": len(items)},
        )

    async def _web_result(self, content: str, *, context: str = "") -> ChatToolResult:
        query = _web_query(content, context=context)
        try:
            search = await self.web_search.search(query, limit=5)
        except WebSearchError as exc:
            return ChatToolResult(
                name="web_search",
                status="error",
                content=f"Web search failed: {exc}",
                payload={"query": query},
            )

        images: list[WebImageResult] = []
        try:
            image_response = await self.web_search.image_search(query, limit=4)
            images = image_response.images
        except WebSearchError:
            images = []

        return ChatToolResult(
            name="web_search",
            status="ready" if search.results else "empty",
            content=_web_search_block(search, images),
            payload={
                "query": search.query,
                "provider": search.provider,
                "count": len(search.results),
                "results": [item.__dict__ for item in search.results],
                "images": [item.__dict__ for item in images],
            },
        )

    async def _product_result(self, content: str, *, context: str = "") -> ChatToolResult:
        query = _product_query(content, context=context)
        try:
            search = await self.web_search.search(query, limit=8)
        except WebSearchError as exc:
            return ChatToolResult(
                name="product_search",
                status="error",
                content=f"Product search failed: {exc}",
                payload={"query": query},
            )

        images: list[WebImageResult] = []
        try:
            image_response = await self.web_search.image_search(query, limit=6)
            images = image_response.images
        except WebSearchError:
            images = []

        candidates = _product_candidates(search)
        return ChatToolResult(
            name="product_search",
            status="ready" if candidates else "empty",
            content=_product_block(query, candidates, images, include_price_hint=False),
            payload={
                "query": query,
                "provider": search.provider,
                "count": len(candidates),
                "products": candidates,
                "images": [item.__dict__ for item in images],
            },
        )

    async def _price_result(self, content: str, *, context: str = "") -> ChatToolResult:
        query = _price_query(content, context=context)
        try:
            search = await self.web_search.search(query, limit=8)
        except WebSearchError as exc:
            return ChatToolResult(
                name="get_prices",
                status="error",
                content=f"Price search failed: {exc}",
                payload={"query": query},
            )

        candidates = _product_candidates(search)
        return ChatToolResult(
            name="get_prices",
            status="ready" if candidates else "empty",
            content=_product_block(query, candidates, [], include_price_hint=True),
            payload={
                "query": query,
                "provider": search.provider,
                "count": len(candidates),
                "products": candidates,
            },
        )

    def _build_outfit_result(self, content: str) -> ChatToolResult:
        query = _wardrobe_query(content)
        items = self.db.list_wardrobe_items(query=query, limit=18)
        if not items:
            items = self.db.list_wardrobe_items(limit=18)

        lines = [
            "Build a complete outfit from chat.",
            "Use owned wardrobe items first. Suggest missing products only if the wardrobe lacks an important piece.",
            "Return one primary outfit, one safer alternative, what to avoid, and whether to save the plan.",
            PERSONALIZATION_POLICY.strip(),
            self.profile.user_context_block(),
        ]
        if items:
            lines.append("\nOwned wardrobe candidates:")
            for item in items:
                parts = [
                    str(item.get("name") or "Unnamed"),
                    f"category={item.get('category') or 'unknown'}",
                ]
                for key in ("subcategory", "brand", "size_label", "fit", "material", "season"):
                    if item.get(key):
                        parts.append(f"{key}={item[key]}")
                if item.get("colors"):
                    parts.append(f"colors={', '.join(item['colors'])}")
                if item.get("occasions"):
                    parts.append(f"occasions={', '.join(item['occasions'])}")
                if item.get("style_tags"):
                    parts.append(f"tags={', '.join(item['style_tags'])}")
                lines.append("- " + "; ".join(parts))
        else:
            lines.append("\nNo owned wardrobe items are saved yet.")

        payload_items: list[dict[str, Any]] = []
        for item in items:
            payload_items.append(
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "category": item.get("category"),
                    "colors": item.get("colors") or [],
                    "brand": item.get("brand"),
                    "season": item.get("season"),
                    "occasions": item.get("occasions") or [],
                    "style_tags": item.get("style_tags") or [],
                    "favorite": item.get("favorite"),
                }
            )

        return ChatToolResult(
            name="build_outfit",
            status="ready" if items else "empty",
            content="\n".join(lines),
            payload={"intent": "outfit_plan", "query": query, "owned_count": len(items), "items": payload_items},
        )


def _is_style_related(content: str) -> bool:
    text = _normalize(content)
    return bool(
        re.search(
            r"\b(moda|fashion|outfit|look|ropa|guardarropa|wardrobe|closet|jeans|botas|botines|zapatos|"
            r"perfumes?|fragancias?|fragrance|maquillaje|makeup|color|colores|estilo|style|prenda|prendas|"
            r"pieza|piezas|silueta|sastre|camiseta|falda|top|cinturon|clutch|chelsea|oxford|slimane|hedi)\b",
            text,
        )
    )


def _should_search_web(content: str) -> bool:
    text = _normalize(content)
    if re.search(r"\b(busca|buscar|busqueda|web|internet|google|investiga|research|precio|comprar|reviews?)\b", text):
        return True
    if re.search(r"\b(conoces|conoce|sabes de|has oido|que es|what is|do you know)\b", text) and _is_style_related(text):
        return True
    if re.search(r"\b(perfume|fragancia|fragrance|marca|brand|producto|product)\b", text) and re.search(
        r"\b(opinion|opiniones|review|vale la pena|recomiendas|conoces|conoce)\b",
        text,
    ):
        return True
    return False


def _should_offer_style_questionnaire(content: str, profile: dict[str, Any]) -> bool:
    if _style_profile_has_enough_context(profile):
        return False
    text = _normalize(content)
    explicit = re.search(
        r"\b(hazme preguntas|preguntame|cuestionario|perfil|conocerme|personaliza|personalizar|"
        r"recomendaciones personalizadas|asistente de moda|experta.*moda|experta.*estilo)\b",
        text,
    )
    broad_recommendation = _is_style_related(text) and re.search(
        r"\b(que me recomiendas|recomendarias|que usar|que me pongo|ayudame con mi estilo|"
        r"no se que usar|look completo|todo|empezar|arrancar)\b",
        text,
    )
    return bool(explicit or broad_recommendation)


def _should_offer_shopping_questionnaire(content: str) -> bool:
    text = _normalize(content)
    if not re.search(r"\b(cuestionario|preguntas|preguntame|selector|seleccionar|dinamico|interactivo)\b", text):
        return False
    if re.search(r"\b(perfil|conocerme|personaliza|personalizar)\b", text) and not re.search(
        r"\b(piezas|prendas|look|outfit|compra|compras|productos|buscar|backend|seleccionar)\b",
        text,
    ):
        return False
    return bool(
        re.search(
            r"\b(piezas|prendas|compra|compras|productos|buscar|backend|seleccionar|opciones)\b",
            text,
        )
        or (re.search(r"\b(look|outfit)\b", text) and not re.search(r"\b(perfil|personaliza|conocerme)\b", text))
    )


def _style_profile_has_enough_context(profile: dict[str, Any]) -> bool:
    key_fields = ("gender_identity", "age_range", "style_keywords", "primary_occasion", "style_focus")
    completed = sum(1 for field in key_fields if str(profile.get(field) or "").strip())
    return completed >= 4


def _should_product_search(content: str) -> bool:
    text = _normalize(content)
    if not _is_style_related(text):
        return False
    return bool(
        re.search(
            r"\b(que|cuales|cual|recomienda|recomendacion|opciones|productos|perfumes|fragancias|"
            r"comprar|buscar|busca|ricos|bueno|buenos|similar|similares|dupe|alternativas)\b",
            text,
        )
    )


def _should_price_search(content: str) -> bool:
    text = _normalize(content)
    return bool(
        re.search(
            r"\b(precio|precios|cuanto cuesta|valor|disponible|disponibilidad|stock|tienda|tiendas|"
            r"comprar|donde comprar|envio|oferta|sale)\b",
            text,
        )
    )


def _should_plan_outfit(content: str) -> bool:
    text = _normalize(content)
    return bool(
        re.search(
            r"\b(outfit|look|que me pongo|que usar|combinar|combinacion|plan|arma|armame|prepara|"
            r"recomienda.*ropa|estilismo|styling)\b",
            text,
        )
    )


def _is_contextual_style_followup(content: str) -> bool:
    text = _normalize(content)
    if _is_style_related(text):
        return False
    return bool(
        re.search(
            r"\b(arma|armar|armame|plan|busca|buscar|internet|web|opciones|productos|comprar|"
            r"ayudame|si|dale|hagamos|hazlo|seleccionar|cuestionario)\b",
            text,
        )
    )


def _is_shopping_or_plan_followup(content: str) -> bool:
    text = _normalize(content)
    return bool(
        re.search(
            r"\b(busca|buscar|internet|web|comprar|productos|opciones|piezas|prendas|faltan|plan|arma|armar|armame)\b",
            text,
        )
    )


def _should_suggest_preference(content: str) -> bool:
    text = _normalize(content)
    if re.search(r"\b(me gusta|me encantan|prefiero|amo|odio|no me gusta|busco|quiero|me tinca|i like|i prefer)\b", text):
        return _is_style_related(text)
    if "perfume" in text or "fragancia" in text:
        return bool(re.search(r"\b(frambuesa|vainilla|rosa|jazmin|coco|cereza|gourmand|dulce|fresco|amaderado)\b", text))
    return False


def _wardrobe_query(content: str) -> str | None:
    text = _normalize(content)
    keywords = [
        "botas",
        "botines",
        "jeans",
        "pantalon",
        "pantalones",
        "chaqueta",
        "abrigo",
        "vestido",
        "falda",
        "zapatillas",
        "zapatos",
        "bolso",
        "cartera",
        "perfume",
        "maquillaje",
    ]
    for keyword in keywords:
        if keyword in text:
            return keyword
    return None


def _web_query(content: str, *, context: str = "") -> str:
    explicit = _explicit_search_query(content)
    if explicit:
        return _augment_fashion_query(explicit, context=context, intent="web")

    cleaned = _clean_search_instruction(content)
    if _is_low_information_query(cleaned):
        contextual = _contextual_fashion_query(context, intent="web")
        if contextual:
            return contextual

    if _is_style_related(cleaned) or (_is_style_related(context) and _is_contextual_style_followup(content)):
        return _augment_fashion_query(cleaned, context=context, intent="web")
    return cleaned or content.strip()


def _product_query(content: str, *, context: str = "") -> str:
    explicit = _explicit_search_query(content)
    if explicit:
        return _augment_fashion_query(explicit, context=context, intent="product")

    base = _clean_search_instruction(content)
    if _is_low_information_query(base):
        contextual = _contextual_fashion_query(context, intent="product")
        if contextual:
            return contextual
    if _looks_like_generic_missing_pieces(base) and _is_style_related(context):
        contextual = _contextual_fashion_query(context, intent="product")
        if contextual:
            return contextual
    if re.search(r"\bchile|temuco|falabella|ripley|paris|mercado libre|dbs|maicao|zara|mango\b", _normalize(base)):
        return f"{base} producto precio disponibilidad"
    return _augment_fashion_query(base, context=context, intent="product")


def _price_query(content: str, *, context: str = "") -> str:
    explicit = _explicit_search_query(content)
    if explicit:
        return _augment_fashion_query(explicit, context=context, intent="price")

    base = _clean_search_instruction(content)
    if _is_low_information_query(base):
        contextual = _contextual_fashion_query(context, intent="price")
        if contextual:
            return contextual
    if re.search(r"\bchile|falabella|ripley|paris|mercado libre|dbs|maicao|tienda|zara|mango\b", _normalize(base)):
        return f"{base} precio stock disponibilidad"
    return _augment_fashion_query(base, context=context, intent="price")


def _clean_search_instruction(content: str) -> str:
    cleaned = re.sub(
        r"\b(mina|por favor|please|busca|buscar|busqueda|investiga|research|conoces|conoce|sabes de|has oido|internet|web|online)\b",
        " ",
        content,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ?.,;:")
    return cleaned


def _explicit_search_query(content: str) -> str | None:
    match = re.search(r"(?:busqueda sugerida|query sugerida|search query)\s*:\s*(.+)", content, flags=re.IGNORECASE)
    if not match:
        return None
    query = match.group(1).splitlines()[0].strip(" .,:;")
    return query or None


def _query_context(content: str, conversation_context: str) -> str:
    parts = [conversation_context.strip(), content.strip()]
    return "\n".join(part for part in parts if part)


def _is_low_information_query(value: str) -> bool:
    tokens = re.findall(r"[a-zA-Z0-9]+", _normalize(value))
    if not tokens:
        return True
    generic = {
        "a",
        "al",
        "algo",
        "arma",
        "armar",
        "armame",
        "ayuda",
        "ayudame",
        "con",
        "de",
        "del",
        "el",
        "en",
        "esto",
        "haz",
        "hazlo",
        "la",
        "las",
        "lo",
        "los",
        "mi",
        "mis",
        "opciones",
        "plan",
        "por",
        "que",
        "si",
        "un",
        "una",
        "y",
    }
    meaningful = [token for token in tokens if token not in generic]
    return len(meaningful) <= 1


def _looks_like_generic_missing_pieces(value: str) -> bool:
    text = _normalize(value)
    return bool(re.search(r"\b(piezas?|prendas?)\b", text) and re.search(r"\b(faltan|falta|faltantes|missing)\b", text))


def _augment_fashion_query(value: str, *, context: str, intent: str) -> str:
    base = re.sub(r"\s+", " ", value).strip(" ?.,;:")
    if _is_low_information_query(base):
        contextual = _contextual_fashion_query(context, intent=intent)
        if contextual:
            return contextual
    normalized = _normalize(base)
    additions: list[str] = []
    if "hedi" in _normalize(context) and "hedi" not in normalized and "slimane" not in normalized:
        additions.append("Hedi Slimane")
    if intent == "web":
        if _is_style_related(base) and not re.search(r"\breferencias?|looks?|estetica|estilo\b", normalized):
            additions.append("referencias looks estilo")
    else:
        if not re.search(r"\bchile|falabella|ripley|paris|mercado libre|zara|mango\b", normalized):
            additions.append("Chile Zara Mango Falabella Paris Mercado Libre")
        if not re.search(r"\bprecio|precios|stock|disponibilidad|comprar\b", normalized):
            additions.append("precio stock disponibilidad")
    return " ".join(part for part in [base, *additions] if part).strip()


def _contextual_fashion_query(context: str, *, intent: str) -> str | None:
    normalized = _normalize(context)
    if not normalized or not _is_style_related(normalized):
        return None

    aesthetic = _aesthetic_from_context(normalized)
    pieces = _pieces_from_context(normalized)
    if not pieces and aesthetic == "Hedi Slimane":
        pieces = [
            "pantalon sastre negro slim",
            "botines Chelsea negros cuero",
            "camiseta basica blanca algodon",
        ]
    if not pieces:
        pieces = ["prendas clave de moda"]

    if intent == "web":
        query_parts = [aesthetic, "outfit referencias estilo", *pieces[:3]]
    else:
        query_parts = [*pieces[:4], aesthetic, "Chile precio tiendas Zara Mango Falabella Paris Mercado Libre"]
    query = " ".join(part for part in query_parts if part).strip()
    return _short_query(query, limit=180) if query else None


def _aesthetic_from_context(normalized_context: str) -> str:
    if "hedi" in normalized_context or "slimane" in normalized_context:
        return "Hedi Slimane"
    if "old money" in normalized_context:
        return "old money"
    if "minimalista" in normalized_context or "minimalist" in normalized_context:
        return "minimalista"
    if "glam punk" in normalized_context or "rock" in normalized_context:
        return "rock glam punk"
    return ""


def _pieces_from_context(normalized_context: str) -> list[str]:
    patterns = [
        ("pantalon sastre negro slim", r"\bpantalon(?:es)?\b.*\bsastr|sastreria"),
        ("camiseta basica blanca gris algodon", r"\bcamiseta\b|\bpolera\b"),
        ("botines Chelsea negros cuero", r"\bbotines?\b.*\bchelsea\b|\bchelsea\b"),
        ("top saten negro cuello V", r"\btop\b.*\bsaten\b|\bsaten\b|\bseda\b"),
        ("falda midi plisada negra", r"\bfalda\b.*\bplis"),
        ("zapatos Oxford negros suela gruesa", r"\boxford\b"),
        ("cinturon ancho cuero negro hebilla metalica", r"\bcinturon\b"),
        ("clutch metalico plateado", r"\bclutch\b"),
    ]
    pieces: list[str] = []
    for label, pattern in patterns:
        if re.search(pattern, normalized_context) and label not in pieces:
            pieces.append(label)
    return pieces


def _short_query(query: str, *, limit: int = 150) -> str:
    cleaned = re.sub(r"\s+", " ", query).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _product_candidates(search: WebSearchResponse) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for index, item in enumerate(search.results, start=1):
        text = f"{item.title} {item.snippet or ''}"
        price = _extract_price(text)
        availability = _extract_availability(text)
        candidates.append(
            {
                "rank": index,
                "title": item.title,
                "url": item.url,
                "snippet": item.snippet,
                "source": item.source,
                "price": price,
                "availability": availability,
            }
        )
    return candidates


def _product_block(
    query: str,
    candidates: list[dict[str, Any]],
    images: list[WebImageResult],
    *,
    include_price_hint: bool,
) -> str:
    if not candidates:
        return f"No product results for query: {query}"
    lines = [
        f"Query: {query}",
        "These are real web results. Do not invent prices or availability.",
    ]
    if include_price_hint:
        lines.append("If price or availability is null, say it was not visible in the search result.")
    for item in candidates:
        price = item.get("price") or "not visible"
        availability = item.get("availability") or "not visible"
        snippet = f"\nSnippet: {item.get('snippet')}" if item.get("snippet") else ""
        lines.append(
            f"[{item['rank']}] {item['title']}\n"
            f"URL: {item['url']}\n"
            f"Visible price: {price}\n"
            f"Availability hint: {availability}{snippet}"
        )
    if images:
        lines.append("\nProduct/image references:")
        for index, image in enumerate(images, start=1):
            lines.append(f"- image {index}: {image.title}\n  page={image.url}\n  preview={image.thumbnail_url or image.image_url}")
    return "\n\n".join(lines)


def _preference_candidate(content: str) -> ChatToolResult | None:
    text = _normalize(content)
    value: str | None = None
    if "frambuesa" in text and ("perfume" in text or "fragancia" in text):
        value = "Preferencia expresada: perfumes con olor o nota de frambuesa."
    elif re.search(r"\b(me gusta|me encantan|prefiero|amo|no me gusta|odio|busco|quiero)\b", text):
        value = f"Preferencia de estilo expresada: {content.strip()}"
    if not value:
        return None
    key = f"fashion.preferences.{_normalize_key(value)[:90] or 'preference'}"
    return ChatToolResult(
        name="preference_candidate",
        status="pending_confirmation",
        content=(
            "Potential preference to save after explicit confirmation:\n"
            f"- kind=fashion_preference\n- key={key}\n- value={value}"
        ),
        payload={
            "action_type": "save_memory",
            "memory_kind": "fashion_preference",
            "memory_key": key,
            "memory_value": value,
            "confidence": 0.74,
        },
    )


def _extract_price(text: str) -> str | None:
    patterns = [
        r"(?:CLP\s*)?\$\s?\d{1,3}(?:[.\s]\d{3})+(?:,\d+)?",
        r"\b\d{1,3}(?:\.\d{3})+\s*(?:CLP|pesos)?\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return " ".join(match.group(0).split())
    return None


def _extract_availability(text: str) -> str | None:
    normalized = _normalize(text)
    for word in ("disponible", "en stock", "stock", "agotado", "sin stock", "envio", "retiro", "despacho"):
        if word in normalized:
            return word
    return None


def _normalize_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", ".", without_accents.strip().lower())
    return re.sub(r"\.+", ".", slug).strip(".")


def _web_search_block(search: WebSearchResponse, images: list[WebImageResult] | None = None) -> str:
    if not search.results:
        return f"No web results for query: {search.query}"
    lines = [f"Query: {search.query}", f"Provider: {search.provider}"]
    for index, item in enumerate(search.results, start=1):
        snippet = f"\nSnippet: {item.snippet}" if item.snippet else ""
        lines.append(f"[{index}] {item.title}\nURL: {item.url}{snippet}")
    if images:
        lines.append("\nImage references:")
        for index, item in enumerate(images, start=1):
            lines.append(f"- image {index}: {item.title}\n  page={item.url}\n  preview={item.thumbnail_url or item.image_url}")
    return "\n\n".join(lines)


def _normalize(content: str) -> str:
    normalized = unicodedata.normalize("NFKD", content)
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", without_accents).strip().lower()


def _compact(value: str, limit: int) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."
