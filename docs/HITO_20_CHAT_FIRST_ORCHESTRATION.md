# Milestone 20: Chat-First Orchestration

Date: 2026-06-03

## Design Shift

Mina should not depend on panels to perform intelligent work.

Panels remain useful for reviewing data, editing manually, or diagnosing issues, but the primary experience should be:

1. The user talks to Mina through chat/voice.
2. Mina decides which context or tool it needs.
3. Mina uses memory, wardrobe, web search, vision, or planning as internal capabilities.
4. Mina responds in chat with results, sources, and a next step.
5. If memory, a clothing item, or a plan needs to be saved, Mina asks for confirmation before changing stable state.

## Implemented

`ChatToolService` was added.

Current responsibilities:

- detect questions about fashion, style, perfume, makeup, outfits, or wardrobe;
- inject the confirmed profile;
- inject relevant wardrobe items;
- run web searches when the message calls for them;
- search for actual products when the user asks for recommendations or options;
- search for prices/availability when the user asks about stores, stock, or purchases;
- build outfits from candidate items the user already owns;
- try to retrieve visual previews from web search;
- provide web results as citable sources `[1]`, `[2]`;
- propose preferences that can be saved, such as perfume notes or style preferences;
- instruct the model to respond in chat and ask for confirmation before saving.

`AssistantOrchestrator` now runs this layer before calling the LLM in both:

- `/api/chat`;
- `/ws/chat`.

Results are saved as an internal event:

```text
assistant_events.event_type = chat_tool_context
```

## WebSocket Events

Chat emits progress and result events:

```text
tool_status
tool_result
```

English translations of the current Spanish status messages:

- `Checking profile and wardrobe`;
- `Searching for references: <query>`;
- `Searching for actual products: <query>`;
- `Searching for prices and availability: <query>`;
- `Building a plan with your context`.

`tool_result` lets the UI display:

- clickable web references;
- image previews when the provider supplies them;
- cards for actual products;
- visible prices and availability when present in the result;
- a `build_outfit` card with the wardrobe items considered;
- a `style_profile_questionnaire` card to complete the profile when context is missing;
- a preference candidate that can be saved;
- wardrobe count/context.

The desktop UI must show these events inside Mina's message as an activity panel, rather than only as global status text.
Markdown tables are rendered as actual tables with horizontal scrolling so comparative responses do not appear as raw text with `|` characters.

## Response Policy

Mina should respond as a personal curator, especially for fashion, beauty, perfumes, and shopping:

- choose an option when the user asks "which do you like better";
- explain the choice using fragrance notes, occasion, versatility, sources, and saved preferences;
- avoid generic AI disclaimers about lacking a sense of smell, taste, a body, or personal experience;
- do not invent prices, stores, stock, or memories;
- prefer clear sections, bullets, and compact comparisons over long tables.

## Dynamic Questionnaire

Mina can offer an interactive style profile questionnaire when:

- the profile does not yet contain enough style information;
- the user asks for broad recommendations or personalization;
- the user explicitly asks Mina to ask questions.

It should not appear for every specific question. Once fields such as style identity, age range, aesthetic, main occasion, and focus are complete, Mina should reuse that memory across sessions.

When `style_profile_questionnaire` is active, the orchestrator does not call the LLM to write another questionnaire. The interactive card is the primary experience, and the text response should be brief.

When the user clicks the start button (`Empecemos`, meaning "Let's begin" in the current UI), the UI:

- saves the data with `PUT /api/profile`;
- updates stable `user_model` and `fashion_preference` memory;
- collapses the questionnaire into a summary;
- adds a summary to the composer to continue chatting with that context;
- explicitly indicates that Mina must not generate another text questionnaire.

## Confirmation Prompt

If Mina used internal tools and the model does not ask a question, the orchestrator appends a deterministic closing question. An English translation of one example is:

```text
Would you like me to save this as a reference so I can remember it later?
```

This avoids relying on the LLM to always remember to ask for confirmation.

Conversational confirmation can already apply the latest pending action. Translated example:

```text
User: yes, save it
Mina: Done, I saved it to memory: ...
```

Persistence:

```text
pending_actions.status = pending | applied | cancelled
memory_items.kind = fashion_preference | style_reference
```

## Examples

Question:

```text
Mina, do you know this perfume? Is it worth it?
```

Mina should:

- detect that this is a perfume question;
- search for actual products and visual references;
- review related personal/wardrobe context;
- show products/sources and previews if available;
- respond with sources;
- ask whether the user wants to save the preference or reference for recall across sessions.

Confirmation:

```text
yes, save it
```

Mina should save a `fashion_preference` memory item for future sessions.

Question:

```text
Mina, put together an outfit for rainy weather using my boots.
```

Mina should:

- review the profile;
- review the wardrobe;
- use `build_outfit` with candidate items the user owns;
- use visual notes and relevant memories;
- build the plan in chat;
- ask whether the user wants to save the plan or update preferences.

## Remaining Work

This milestone already turns simple confirmations into stable memory. Conversational actions still need to be extended:

- save a wardrobe item from a conversational proposal;
- attach an image directly to chat;
- analyze an attached image and respond in the same thread;
- show action cards that require confirmation;
- save plans/outfits as their own entities, rather than only as memory;
- improve price/stock extraction with more structured shopping providers.

## Verification

```powershell
.venv\Scripts\python -m unittest discover -s tests
cd desktop
npm run build
```
