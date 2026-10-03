# Milestones 16-19: Research, Planning, and Wardrobe Extraction

Date: 2026-06-03

## Goal

Connect Mina's existing fashion capabilities:

- personal profile;
- wardrobe;
- image gallery;
- local/external vision;
- web search;
- text providers.

The goal is for Mina to research with sources, propose outfits using actual user context, and turn an uploaded image into a wardrobe item that can be saved.

## Milestone 16: Research Brief with Citations

Endpoint:

```text
POST /api/style/research
```

Main inputs:

- `query`;
- optional search provider;
- optional text provider/model.

Flow:

1. `WebSearchService` searches for external results.
2. `StyleAssistantService` passes those results to the LLM as numbered sources.
3. The LLM returns a Markdown brief with citations such as `[1]`.

Important rule: Mina must not cite sources outside the supplied list.

## Milestone 17: Outfit Planner

Endpoint:

```text
POST /api/style/outfit-plan
```

Context used:

- saved profile;
- wardrobe items;
- visual analyses saved with images;
- optional web results;
- selected text provider/model.

The result is Markdown and must distinguish between:

- clothing the user already owns;
- missing or suggested pieces;
- reasons based on the profile/preferences;
- web citations when external sources were used.

## Milestone 18: Clothing Extraction from an Image

Endpoint:

```text
POST /api/wardrobe/images/{image_id}/extract
```

Flow:

1. Mina sends the image to `VisionService`.
2. The prompt requires compact JSON and a response only in Spanish or English.
3. `StyleAssistantService` parses the JSON.
4. If the model does not return valid JSON, a fallback draft is created with raw notes.

The draft includes:

- name;
- category;
- subtype;
- colors;
- material;
- brand;
- fit;
- season;
- occasions;
- style tags;
- notes;
- confidence;
- `source_image_id`.

## Milestone 19: Save the Extracted Draft as an Actual Item

The `Wardrobe` UI shows an `Extracted item draft` panel after extracting an image.

Actions:

- `Load form`: loads the draft into the form for editing.
- `Save item`: creates an actual `wardrobe_item`.
- When saved, the image is linked to the item using:

```text
PATCH /api/wardrobe/images/{image_id}
```

This maintains the relationship between the photo, clothing item, and `wardrobe_model` memory.

## UI

The `Wardrobe` view now includes:

- a `Brief` button in `Web research`;
- an `Outfit planner` subpanel;
- an `Extract` button on each image;
- an extracted draft panel.

## Limitations

- Web search is still text-based; it does not automatically download or compare external images.
- Draft quality depends on the vision model.
- If the model returns unstructured text, Mina saves a fallback draft for the user to edit.
- New stable preference memory is not saved outside the existing memory/reflection flow.

## Verification

```powershell
.venv\Scripts\python -m unittest discover -s tests
cd desktop
npm run build
```
