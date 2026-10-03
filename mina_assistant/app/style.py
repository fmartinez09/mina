from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mina_assistant.app.db import SQLiteStore
from mina_assistant.app.llm import LLMResponse, LLMService
from mina_assistant.app.profile import PERSONALIZATION_POLICY, ProfileService
from mina_assistant.app.web_search import WebSearchResponse, WebSearchService


STYLE_SYSTEM_PROMPT = """You are Mina, a personal style assistant.
Answer only in Spanish or English. Prefer Spanish when the request is Spanish or unclear.
Be practical, concise, tasteful, and honest.
Use saved profile and wardrobe context only when it is relevant.
When web sources are provided, cite them with bracket references like [1].
Never cite a source that is not in the provided source list.
If the available evidence is weak, say so clearly.
"""

WARDROBE_EXTRACTION_PROMPT = """Analyze this wardrobe image and extract one primary garment, accessory, makeup item, perfume, or style reference.
Answer only in Spanish or English. Never answer in Chinese.
Return only one compact JSON object. Do not include Markdown, comments, or text outside JSON.

JSON keys:
{
  "name": "short human name",
  "category": "top|bottom|outerwear|dress|shoes|accessory|bag|perfume|makeup|reference|other",
  "subcategory": "optional subtype or null",
  "colors": ["color names"],
  "material": "material or null",
  "brand": "visible brand or null",
  "size_label": "visible size or null",
  "fit": "fit/silhouette or null",
  "season": "season/weather use or null",
  "occasions": ["occasions"],
  "style_tags": ["style keywords"],
  "notes": "brief fit, styling, uncertainty, or visual notes",
  "favorite": false,
  "confidence": 0.0
}

Use null when unknown. Keep arrays short. Set confidence between 0 and 1.
"""

ALLOWED_CATEGORIES = {
    "top",
    "bottom",
    "outerwear",
    "dress",
    "shoes",
    "accessory",
    "bag",
    "perfume",
    "makeup",
    "reference",
    "other",
}


@dataclass(frozen=True)
class StyleResearchResult:
    query: str
    brief: str
    provider: str
    model: str
    search: WebSearchResponse


@dataclass(frozen=True)
class OutfitPlanResult:
    prompt: str
    plan: str
    provider: str
    model: str
    search: WebSearchResponse | None = None


class StyleAssistantService:
    def __init__(
        self,
        *,
        db: SQLiteStore,
        llm: LLMService,
        profile: ProfileService,
        web_search: WebSearchService,
    ) -> None:
        self.db = db
        self.llm = llm
        self.profile = profile
        self.web_search = web_search

    async def research_brief(
        self,
        *,
        query: str,
        search_provider: str | None = None,
        search_limit: int | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> StyleResearchResult:
        search = await self.web_search.search(query, provider=search_provider, limit=search_limit)
        source_block = _web_source_block(search)
        response = await self.llm.chat(
            [
                {"role": "system", "content": STYLE_SYSTEM_PROMPT + "\n" + PERSONALIZATION_POLICY},
                {
                    "role": "user",
                    "content": (
                        f"Research query: {query.strip()}\n\n"
                        f"Sources:\n{source_block}\n\n"
                        "Create a concise style research brief with:\n"
                        "- key takeaways;\n"
                        "- practical guidance for outfits, colors, silhouettes, shopping, or styling;\n"
                        "- caveats or uncertainty;\n"
                        "- citations using [1], [2], etc. where relevant.\n"
                        "Do not invent facts beyond the source list."
                    ),
                },
            ],
            provider=provider,
            model=model,
            temperature=0.25,
        )
        return StyleResearchResult(
            query=search.query,
            brief=response.content,
            provider=response.provider,
            model=response.model,
            search=search,
        )

    async def outfit_plan(
        self,
        *,
        prompt: str,
        web_query: str | None = None,
        search_provider: str | None = None,
        search_limit: int | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> OutfitPlanResult:
        search: WebSearchResponse | None = None
        if web_query and web_query.strip():
            search = await self.web_search.search(web_query, provider=search_provider, limit=search_limit)

        profile = self.profile.get_profile()
        wardrobe_items = self.db.list_wardrobe_items(limit=80)
        wardrobe_images = self.db.list_wardrobe_images(limit=30)
        response = await self.llm.chat(
            [
                {"role": "system", "content": STYLE_SYSTEM_PROMPT + "\n" + PERSONALIZATION_POLICY},
                {
                    "role": "user",
                    "content": (
                        f"User request:\n{prompt.strip()}\n\n"
                        f"Profile context:\n{_profile_block(profile)}\n\n"
                        f"{self.profile.user_context_block()}\n\n"
                        f"Owned wardrobe:\n{_wardrobe_block(wardrobe_items)}\n\n"
                        f"Visual notes from uploaded images:\n{_image_notes_block(wardrobe_images)}\n\n"
                        f"Web sources:\n{_web_source_block(search) if search else 'No web sources provided.'}\n\n"
                        "Create a practical outfit plan in Markdown. Include:\n"
                        "- a primary outfit formula;\n"
                        "- owned wardrobe items to use by name;\n"
                        "- missing pieces or shopping targets only if needed;\n"
                        "- why it works for the user's profile/preferences;\n"
                        "- weather/occasion caveats when relevant;\n"
                        "- web citations [1], [2] only when web sources are used.\n"
                        "Do not pretend uncertain profile details are confirmed."
                    ),
                },
            ],
            provider=provider,
            model=model,
            temperature=0.35,
        )
        return OutfitPlanResult(
            prompt=prompt.strip(),
            plan=response.content,
            provider=response.provider,
            model=response.model,
            search=search,
        )

    def extraction_prompt(self, custom_prompt: str | None = None) -> str:
        cleaned = (custom_prompt or "").strip()
        if not cleaned:
            return WARDROBE_EXTRACTION_PROMPT
        return f"{WARDROBE_EXTRACTION_PROMPT}\n\nExtra user instruction:\n{cleaned}"

    def wardrobe_draft_from_analysis(self, analysis: str, *, image: dict[str, Any]) -> dict[str, Any]:
        parsed = _extract_json_object(analysis) or {}
        name = _clean_string(parsed.get("name")) or _name_from_image(image)
        category = _clean_string(parsed.get("category"), lowercase=True) or "other"
        if category not in ALLOWED_CATEGORIES:
            category = "other"

        draft = {
            "source_image_id": int(image["id"]),
            "name": _truncate(name, 180),
            "category": _truncate(category, 120),
            "subcategory": _truncate(_clean_string(parsed.get("subcategory")), 120),
            "colors": _clean_list(parsed.get("colors"), max_items=16),
            "material": _truncate(_clean_string(parsed.get("material")), 120),
            "brand": _truncate(_clean_string(parsed.get("brand")), 120),
            "size_label": _truncate(_clean_string(parsed.get("size_label")), 80),
            "fit": _truncate(_clean_string(parsed.get("fit")), 120),
            "season": _truncate(_clean_string(parsed.get("season")), 120),
            "occasions": _clean_list(parsed.get("occasions"), max_items=20),
            "style_tags": _clean_list(parsed.get("style_tags"), max_items=24),
            "notes": _truncate(_clean_string(parsed.get("notes")) or analysis.strip(), 2000),
            "favorite": bool(parsed.get("favorite")) if "favorite" in parsed else False,
            "confidence": _clean_confidence(parsed.get("confidence")),
            "source": "vision",
            "source_id": str(image["id"]),
            "raw_analysis": _truncate(analysis.strip(), 8000) or "",
        }
        return draft


def _web_source_block(search: WebSearchResponse | None) -> str:
    if not search or not search.results:
        return "No sources."
    lines: list[str] = []
    for index, item in enumerate(search.results, start=1):
        snippet = f"\nSnippet: {item.snippet}" if item.snippet else ""
        lines.append(f"[{index}] {item.title}\nURL: {item.url}{snippet}")
    return "\n\n".join(lines)


def _profile_block(profile: dict[str, Any]) -> str:
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
    return "\n".join(lines) if lines else "No confirmed profile details yet."


def _wardrobe_block(items: list[dict[str, Any]]) -> str:
    if not items:
        return "No saved wardrobe items yet."
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
        lines.append("- " + "; ".join(parts))
    return "\n".join(lines)


def _image_notes_block(images: list[dict[str, Any]]) -> str:
    notes: list[str] = []
    for image in images:
        analysis = str(image.get("analysis") or "").strip()
        if not analysis:
            continue
        label = _name_from_image(image)
        notes.append(f"- image {image['id']} ({label}): {_truncate(analysis, 700)}")
    return "\n".join(notes) if notes else "No analyzed image notes yet."


def _extract_json_object(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.replace("```json", "```").replace("```JSON", "```")
        cleaned = cleaned.strip("`").strip()

    start = cleaned.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(cleaned)):
        char = cleaned[index]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                candidate = cleaned[start : index + 1]
                try:
                    loaded = json.loads(candidate)
                except json.JSONDecodeError:
                    return None
                return loaded if isinstance(loaded, dict) else None
    return None


def _clean_string(value: Any, *, lowercase: bool = False) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return None
    cleaned = " ".join(str(value).split()).strip()
    if not cleaned or cleaned.lower() in {"null", "none", "unknown", "n/a"}:
        return None
    return cleaned.lower() if lowercase else cleaned


def _clean_list(value: Any, *, max_items: int) -> list[str]:
    if value is None:
        raw: list[Any] = []
    elif isinstance(value, str):
        raw = value.replace("\n", ",").split(",")
    elif isinstance(value, list):
        raw = value
    else:
        raw = []

    seen: set[str] = set()
    result: list[str] = []
    for item in raw:
        cleaned = _clean_string(item)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(_truncate(cleaned, 80) or cleaned)
        if len(result) >= max_items:
            break
    return result


def _clean_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.45
    return max(0.0, min(confidence, 1.0))


def _truncate(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "..."


def _name_from_image(image: dict[str, Any]) -> str:
    original = str(image.get("original_name") or "").strip()
    if original:
        return Path(original).stem.replace("_", " ").replace("-", " ").strip() or original
    return f"Image {image.get('id', '')} item".strip()
