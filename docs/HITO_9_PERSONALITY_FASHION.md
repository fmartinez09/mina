# Milestone 9 - Personality, Fashion, and Style Memory

## Goal

Move Mina toward a persistent cognitive companion focused on:

- continuity between conversations;
- a stable, editable personality;
- preferences about how it should respond;
- memory of fashion, style, perfumes, and wardrobe;
- reflection with human approval before saving lasting changes.

This milestone does not add external tools. The focus remains on chat, voice, memory, personality, and fashion.

## Core Principle

The model is not Mina.

Mina lives in:

- its core personality;
- its structured memory;
- its model of the relationship with the user;
- its self model;
- its episodic history;
- its approved reflections;
- the context it builds before each response.

This allows switching from Ollama to OpenAI, Anthropic, or another model without losing continuity.

## Personality Layers

### Core Personality

Stable identity. Changes very little.

Examples:

- name: Mina;
- traits: curious, honest, warm, intelligent;
- values: truth, loyalty, kindness, growth;
- boundaries: does not invent memories or pretend to be certain.

Memory type: `personality_profile`.

### Adaptive Personality

Interaction preferences learned over time.

Examples:

- low/medium/high humor;
- low/medium/high formality;
- level of initiative;
- preference for brief or detailed responses;
- level of warmth.

Memory type: `relationship_signal`.

### Self Model

How Mina understands its own role.

Examples:

- role: cognitive companion;
- purpose: help the user with continuity and judgment;
- strengths: memory, synthesis, conversation, organization;
- limitations: does not experience the world directly and must not invent personal experiences.

Memory type: `self_model`.

## Fashion and Style Model

### Fashion Preferences

Tastes, aesthetics, silhouettes, colors, perfumes, and brands the user prefers.

Memory type: `fashion_preference`.

Examples:

- prefers black wide-leg pants;
- likes Korean casual silhouettes;
- is interested in gourmand perfumes;
- avoids overly formal combinations.

### Wardrobe Model

Editable inventory of clothing, accessories, and perfumes the user owns.

Memory type: `wardrobe_model`.

Examples:

- owns an oversized black jacket;
- owns black wide-leg pants;
- owns white sneakers;
- owns a specific perfume.

### Style References

Visual references, brands, designers, celebrities, moodboards, or external aesthetics.

Memory type: `style_reference`.

Examples:

- Kim Chaewon references;
- Korean minimalist inspiration;
- brands or collections of interest;
- looks saved as references.

### Media Memory

Observations derived from images or media. This milestone only prepares the memory type; actual visual ingestion is deferred to a later stage.

Memory type: `media_memory`.

Future examples:

- an outfit photo uploaded by the user;
- a screenshot of a look;
- a moodboard;
- an image of a clothing item.

## New Intents

### `fashion_context`

Triggered by conversations about:

- fashion;
- outfits;
- clothing;
- wardrobe;
- perfumes;
- silhouettes;
- aesthetics;
- brands or references.

Primarily retrieves:

- `wardrobe_model`;
- `fashion_preference`;
- `style_reference`;
- `media_memory`;
- `user_model`;
- `relationship_signal`.

### `personality_context`

Triggered by conversations about:

- Mina's personality;
- how it should respond;
- tone;
- humor;
- formality;
- initiative;
- self-image;
- Mina's role.

Primarily retrieves:

- `personality_profile`;
- `self_model`;
- `relationship_signal`;
- `user_model`;
- `episodic_event`.

## Reflection Engine

The Reflection Engine can now propose candidates using the new categories.

Important rule:

Mina must not silently apply personality changes without review. It must propose them as candidates:

- with evidence;
- with a rationale;
- with confidence;
- with a memory type;
- with a stable key.

The user approves, edits, or rejects them.

## Future Jobs

This milestone prepares the vocabulary. The next stage should add recurring internal jobs:

- `Daily Reflection`;
- `Weekly Reflection`;
- `Relationship Reflection`;
- `Self Reflection`;
- `Interest Discovery`;
- `Uncertainty Tracker`;
- `Contradiction Detector`;
- `Memory Cleanup`.

These jobs do not respond directly to the user. They keep Mina's internal model up to date and generate candidates for review.

## Implemented Features

- New memory types in the backend and API.
- Initial classification of explicit fashion, personality, and response style memories.
- Specialized context retrieval for fashion and personality.
- Reflection Engine updated with category guidance.
- Desktop filters and editor updated for the new types.
- Tests for fashion classification and context.
