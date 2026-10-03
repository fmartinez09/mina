# Milestone 14 - Controlled Web Search

## Goal

Let Mina search for external fashion references, products, trends, or inspiration without automatically mixing those results into stable memory.

## Implemented Features

- `WebSearchService`.
- `POST /api/web/search` endpoint.
- Providers:
  - `duckduckgo`: fallback without an API key, using locally parsed HTML;
  - `brave`: structured API when `MINA_BRAVE_SEARCH_API_KEY` is configured.
- `Web research` panel in `Wardrobe`.
- Normalized results with:
  - title;
  - URL;
  - snippet;
  - provider.

## Configuration

Set these values in `.env`:

```dotenv
MINA_WEB_SEARCH_PROVIDER=duckduckgo
MINA_BRAVE_SEARCH_API_KEY=
MINA_WEB_SEARCH_MAX_RESULTS=6
```

For Brave:

```dotenv
MINA_WEB_SEARCH_PROVIDER=brave
MINA_BRAVE_SEARCH_API_KEY=your_key
```

## Decision

Web search does not automatically save memory. Mina can use results as visible context, but any stable preference must be saved through approved memory or an explicit user action.

## Next Step

Integrate web results into chat as citable context and let Mina compare external results with the wardrobe.
