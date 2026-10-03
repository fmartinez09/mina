# Milestone 11 - Actual Wardrobe Inventory

## Goal

Create an editable inventory of clothing, accessories, perfumes, and makeup that Mina can consult to make concrete suggestions.

## Implemented Features

- `wardrobe_items` table.
- `wardrobe_images` table prepared for the next milestone.
- Endpoints:
  - `GET /api/wardrobe/items`;
  - `POST /api/wardrobe/items`;
  - `PATCH /api/wardrobe/items/{item_id}`;
  - `DELETE /api/wardrobe/items/{item_id}`.
- `Wardrobe` view in Mina Desktop.
- Clothing CRUD with:
  - name;
  - category;
  - subtype;
  - colors;
  - material;
  - brand;
  - size;
  - fit;
  - season;
  - occasions;
  - style tags;
  - notes;
  - favorite flag.

## Architecture Decision

The wardrobe has its own table because it needs a UI, filters, deletion, images, and structured queries.

Each item is also synchronized as `wardrobe_model` memory with the key `wardrobe.items.{id}`. This lets Mina use the wardrobe in its existing context without waiting for a new reasoning layer.

## Deletion

Clothing items are soft-deleted in `wardrobe_items`, and their associated `wardrobe_model` memory is also removed.

## Image Support Preparation

The `wardrobe_images` table is ready to:

- upload photos;
- associate them with clothing items;
- store thumbnails;
- store vision analysis;
- delete images without breaking the associated item.

The gallery and upload UI are deferred to the next milestone.

## Next Step

Milestone 12: image gallery and uploads.

Milestone 13: `VisionService` with local Qwen and external OpenAI.
