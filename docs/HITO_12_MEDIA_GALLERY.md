# Milestone 12 - Image Gallery

## Goal

Let Mina store actual wardrobe images or visual references, display them in the desktop app, and allow their deletion.

## Implemented Features

- `MINA_MEDIA_DIR` configuration.
- Static `/media` mount.
- `MediaService` to:
  - validate base64 data URLs;
  - accept `jpeg`, `png`, `webp`, and `gif`;
  - save files in `data/media`;
  - detect basic PNG/JPEG dimensions;
  - list images;
  - soft-delete image records and remove their local files.
- Endpoints:
  - `GET /api/wardrobe/images`;
  - `POST /api/wardrobe/images`;
  - `DELETE /api/wardrobe/images/{image_id}`.
- Gallery in the `Wardrobe` view in Mina Desktop.
- Image uploads from the UI.
- Optional image association with existing clothing items.
- Image counts per clothing item updated from SQLite.

## Architecture Decision

Images are stored as local files, and their metadata lives in SQLite. This avoids storing large blobs in the database and keeps the inventory easy to back up.

The `wardrobe_images` table stores:

- associated item;
- local path;
- original filename;
- MIME type;
- dimensions;
- visual analysis;
- soft deletion state.

## Current Limitation

Actual thumbnails are not generated yet. The UI uses the original image as a preview. Generating thumbnails requires an image processing dependency or a local library such as Pillow.

## Next Step

Milestone 13: analyze images with local or external vision models.
