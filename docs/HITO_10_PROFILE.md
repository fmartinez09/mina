# Milestone 10 - Personal Profile

## Goal

Give Mina a confirmed user profile so it does not rely solely on inferences from chat.

## Implemented Features

- `GET /api/profile` endpoint.
- `PUT /api/profile` endpoint.
- `Profile` view in Mina Desktop.
- Core fields:
  - preferred name;
  - home city or climate;
  - height;
  - body or proportion notes;
  - top, bottom, and shoe sizes;
  - fit preferences;
  - favorite and avoided colors;
  - style keywords;
  - comfort constraints;
  - budget or brands;
  - privacy preferences for images/web.

## Architecture Decision

The profile is stored as confirmed memory in `memory_items`, using stable `profile.*` keys.

This lets Mina use the profile immediately in conversational context without adding a duplicate table.

## Rules

- Empty fields remove the associated memory.
- The profile is not automatically inferred from arbitrary statements.
- Sensitive preferences must be confirmed or edited by the user.

## Next Step

Use these details when analyzing images and recommending outfits, especially city/climate, sizes, comfort, and fit preferences.
