const state = {
  sessions: [],
  currentSessionId: null,
  messages: [],
  textProviders: [],
  ttsProviders: [],
  busy: false,
};

const elements = {
  sessionList: document.querySelector("#sessionList"),
  messages: document.querySelector("#messages"),
  composer: document.querySelector("#composer"),
  messageInput: document.querySelector("#messageInput"),
  sendButton: document.querySelector("#sendButton"),
  providerSelect: document.querySelector("#providerSelect"),
  modelInput: document.querySelector("#modelInput"),
  modelOptions: document.querySelector("#modelOptions"),
  ttsProviderSelect: document.querySelector("#ttsProviderSelect"),
  voiceInput: document.querySelector("#voiceInput"),
  voiceOptions: document.querySelector("#voiceOptions"),
  conversationTitle: document.querySelector("#conversationTitle"),
  statusText: document.querySelector("#statusText"),
  statusDot: document.querySelector("#statusDot"),
  newSessionButton: document.querySelector("#newSessionButton"),
  refreshButton: document.querySelector("#refreshButton"),
};

function setStatus(text, kind = "busy") {
  elements.statusText.textContent = text;
  elements.statusDot.classList.toggle("ready", kind === "ready");
  elements.statusDot.classList.toggle("error", kind === "error");
}

function setBusy(value) {
  state.busy = value;
  elements.sendButton.disabled = value;
  elements.messageInput.disabled = value;
  elements.providerSelect.disabled = value;
  elements.modelInput.disabled = value;
  elements.ttsProviderSelect.disabled = value;
  elements.voiceInput.disabled = value;
}

function getOutputMode() {
  return document.querySelector("input[name='outputMode']:checked")?.value ?? "text";
}

function getTextProvider() {
  return elements.providerSelect.value || null;
}

function getTextModel() {
  const value = elements.modelInput.value.trim();
  return value || null;
}

function getTtsProvider() {
  return elements.ttsProviderSelect.value || null;
}

function getVoice() {
  const value = elements.voiceInput.value.trim();
  return value || null;
}

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("es-CL", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function normalizeSessionTitle(session) {
  return session.title || "Untitled conversation";
}

function providerLabel(provider) {
  return provider?.label || provider?.name || "";
}

function selectedTextProvider() {
  return state.textProviders.find((provider) => provider.name === getTextProvider());
}

function selectedTtsProvider() {
  return state.ttsProviders.find((provider) => provider.name === getTtsProvider());
}

function renderSessions() {
  elements.sessionList.innerHTML = "";

  if (state.sessions.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "No saved sessions.";
    elements.sessionList.append(empty);
    return;
  }

  for (const session of state.sessions) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "session-button";
    if (session.id === state.currentSessionId) {
      button.classList.add("active");
    }
    button.dataset.sessionId = session.id;

    const title = document.createElement("span");
    title.className = "session-title";
    title.textContent = normalizeSessionTitle(session);

    const meta = document.createElement("span");
    meta.className = "session-meta";
    meta.textContent = `${session.message_count} messages - ${formatDate(session.updated_at)}`;

    button.append(title, meta);
    button.addEventListener("click", () => selectSession(session.id));
    elements.sessionList.append(button);
  }
}

function renderMessages() {
  elements.messages.innerHTML = "";

  if (state.messages.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.innerHTML = "<strong>New conversation</strong><span>No messages yet.</span>";
    elements.messages.append(empty);
    return;
  }

  for (const message of state.messages) {
    elements.messages.append(renderMessage(message));
  }

  elements.messages.scrollTop = elements.messages.scrollHeight;
}

function renderMessage(message) {
  const article = document.createElement("article");
  article.className = `message ${message.role}`;

  const header = document.createElement("div");
  header.className = "message-header";

  const role = document.createElement("span");
  role.textContent = message.role === "user" ? "You" : "Mina";

  const meta = document.createElement("span");
  const details = [];
  if (message.model) details.push(message.model);
  if (message.tokens) details.push(`${message.tokens} tokens`);
  if (message.created_at) details.push(formatDate(message.created_at));
  meta.textContent = details.join(" - ");

  const content = document.createElement("p");
  content.className = "message-content";
  content.textContent = message.content;

  header.append(role, meta);
  article.append(header, content);

  if (message.audio_url) {
    const audio = document.createElement("audio");
    audio.className = "audio-player";
    audio.controls = true;
    audio.preload = "metadata";
    audio.src = message.audio_url;
    article.append(audio);
  }

  return article;
}

function renderTextProviders(defaultProviderName) {
  elements.providerSelect.innerHTML = "";

  for (const provider of state.textProviders) {
    const option = document.createElement("option");
    option.value = provider.name;
    option.textContent = provider.available
      ? providerLabel(provider)
      : `${providerLabel(provider)} (not configured)`;
    option.disabled = !provider.available;
    elements.providerSelect.append(option);
  }

  const preferred = state.textProviders.find((provider) => {
    return provider.name === defaultProviderName && provider.available;
  });
  const firstAvailable = state.textProviders.find((provider) => provider.available);
  const selected = preferred || firstAvailable || state.textProviders[0];
  if (selected) {
    elements.providerSelect.value = selected.name;
  }
  updateModelOptions();
}

function updateModelOptions() {
  const provider = selectedTextProvider();
  elements.modelOptions.innerHTML = "";

  if (!provider) {
    elements.modelInput.value = "";
    return;
  }

  for (const model of provider.models || []) {
    const option = document.createElement("option");
    option.value = model;
    elements.modelOptions.append(option);
  }

  const current = elements.modelInput.value.trim();
  const currentExists = (provider.models || []).includes(current);
  if (!current || !currentExists) {
    elements.modelInput.value = provider.default_model || provider.models?.[0] || "";
  }
}

function renderTtsProviders(defaultProviderName) {
  elements.ttsProviderSelect.innerHTML = "";

  for (const provider of state.ttsProviders) {
    const option = document.createElement("option");
    option.value = provider.name;
    option.textContent = provider.available
      ? providerLabel(provider)
      : `${providerLabel(provider)} (not configured)`;
    option.disabled = !provider.available;
    elements.ttsProviderSelect.append(option);
  }

  const preferred = state.ttsProviders.find((provider) => {
    return provider.name === defaultProviderName && provider.available;
  });
  const firstAvailable = state.ttsProviders.find((provider) => provider.available);
  const selected = preferred || firstAvailable || state.ttsProviders[0];
  if (selected) {
    elements.ttsProviderSelect.value = selected.name;
  }
  updateVoiceOptions();
}

function updateVoiceOptions() {
  const provider = selectedTtsProvider();
  elements.voiceOptions.innerHTML = "";

  if (!provider) {
    elements.voiceInput.value = "";
    return;
  }

  for (const voice of provider.voices || []) {
    const option = document.createElement("option");
    option.value = voice.id;
    option.label = voice.label || voice.id;
    elements.voiceOptions.append(option);
  }

  const voiceIds = (provider.voices || []).map((voice) => voice.id);
  const current = elements.voiceInput.value.trim();
  if (!current || !voiceIds.includes(current)) {
    elements.voiceInput.value = provider.default_voice || voiceIds[0] || "";
  }
}

function updateConversationTitle() {
  const active = state.sessions.find((session) => session.id === state.currentSessionId);
  elements.conversationTitle.textContent = active ? normalizeSessionTitle(active) : "New conversation";
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const payload = await response.json();
      detail = typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail);
    } catch {
      // Keep status text.
    }
    throw new Error(detail);
  }
  return response.json();
}

async function loadHealth() {
  const health = await fetchJson("/api/health");
  state.textProviders = health.text_providers ?? [];
  state.ttsProviders = health.tts_providers ?? [];

  if (state.textProviders.length === 0) {
    state.textProviders = [{
      name: "ollama",
      label: "Ollama",
      available: health.ollama_available,
      default_model: health.ollama_models?.[0] || "gemma4:e4b ",
      models: health.ollama_models ?? [],
    }];
  }

  renderTextProviders(health.text_provider);
  renderTtsProviders(health.tts_provider);

  const textProvider = selectedTextProvider();
  const ttsProvider = selectedTtsProvider();
  const textReady = textProvider?.available;
  const ttsReady = ttsProvider?.available;

  if (textReady) {
    const ttsStatus = ttsReady ? `TTS: ${providerLabel(ttsProvider)}` : "TTS unavailable";
    setStatus(`${providerLabel(textProvider)} ready - ${ttsStatus}`, ttsReady ? "ready" : "busy");
  } else {
    setStatus("No text provider configured", "error");
  }
}

async function loadSessions() {
  state.sessions = await fetchJson("/api/sessions?limit=50");
  renderSessions();
  updateConversationTitle();
}

async function selectSession(sessionId) {
  state.currentSessionId = sessionId;
  state.messages = await fetchJson(`/api/sessions/${sessionId}/messages`);
  renderSessions();
  renderMessages();
  updateConversationTitle();
}

function startNewSession() {
  state.currentSessionId = null;
  state.messages = [];
  renderSessions();
  renderMessages();
  updateConversationTitle();
  elements.messageInput.focus();
}

function chatWebSocketUrl() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${window.location.host}/ws/chat`;
}

async function sendMessage(content) {
  setBusy(true);
  setStatus("Connecting response", "busy");
  const outputMode = getOutputMode();
  const provider = getTextProvider();
  const model = getTextModel();

  const userMessage = {
    role: "user",
    content,
    created_at: new Date().toISOString(),
  };
  const assistantMessage = {
    role: "assistant",
    content: "",
    created_at: new Date().toISOString(),
    model: provider && model ? `${provider}/${model}` : model || "",
  };
  state.messages.push(userMessage);
  state.messages.push(assistantMessage);
  renderMessages();

  try {
    await streamMessage(content, assistantMessage, outputMode, provider, model);
  } catch (error) {
    state.messages.push({
      role: "system",
      content: `Error: ${error.message}`,
      created_at: new Date().toISOString(),
    });
    renderMessages();
    setStatus("Error", "error");
  } finally {
    setBusy(false);
    elements.messageInput.focus();
  }
}

function shouldSynthesizeAudio(outputMode) {
  return outputMode === "voice" || outputMode === "both";
}

async function synthesizeSpeech(text, messageId) {
  return fetchJson("/api/tts", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      text,
      message_id: messageId,
      provider: getTtsProvider(),
      voice: getVoice(),
    }),
  });
}

async function playAudio(audioUrl) {
  try {
    const audio = new Audio(audioUrl);
    await audio.play();
  } catch {
    // Browser autoplay rules can block delayed playback; inline controls remain visible.
  }
}

function attachAudioToPersistedMessage(messageId, ttsResult) {
  const message = state.messages.find((item) => item.id === messageId);
  if (message) {
    message.audio_url = ttsResult.audio_url;
    message.audio_provider = ttsResult.provider;
    message.audio_voice = ttsResult.voice;
  }
  return message;
}

function streamMessage(content, assistantMessage, outputMode, provider, model) {
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(chatWebSocketUrl());
    let completed = false;

    socket.addEventListener("open", () => {
      socket.send(
        JSON.stringify({
          content,
          session_id: state.currentSessionId,
          input_mode: "text",
          output_mode: outputMode,
          provider,
          model,
        })
      );
    });

    socket.addEventListener("message", async (event) => {
      const payload = JSON.parse(event.data);

      if (payload.type === "status") {
        setStatus("Processing response", "busy");
        return;
      }

      if (payload.type === "turn_started") {
        state.currentSessionId = payload.session_id;
        assistantMessage.model = payload.model || assistantMessage.model;
        setStatus("Generating response", "busy");
        return;
      }

      if (payload.type === "assistant_chunk") {
        assistantMessage.content += payload.delta || "";
        assistantMessage.model = payload.model || assistantMessage.model;
        renderMessages();
        setStatus("Receiving response", "busy");
        return;
      }

      if (payload.type === "assistant_message") {
        completed = true;
        const data = payload.data;
        state.currentSessionId = data.session_id;
        assistantMessage.content = data.content;
        assistantMessage.model = data.model;
        assistantMessage.tokens = data.tokens_used;
        try {
          state.messages = await fetchJson(`/api/sessions/${data.session_id}/messages`);
          if (shouldSynthesizeAudio(outputMode)) {
            setStatus("Synthesizing voice", "busy");
            const ttsResult = await synthesizeSpeech(data.content, data.assistant_message_id);
            const message = attachAudioToPersistedMessage(data.assistant_message_id, ttsResult);
            renderMessages();
            if (message?.audio_url) {
              await playAudio(message.audio_url);
            }
          }
          await loadSessions();
          renderMessages();
          setStatus("Ready", "ready");
          socket.close();
          resolve();
        } catch (error) {
          socket.close();
          reject(error);
        }
        return;
      }

      if (payload.type === "error") {
        completed = true;
        socket.close();
        reject(new Error(payload.detail || "Streaming error"));
      }
    });

    socket.addEventListener("error", () => {
      completed = true;
      reject(new Error("Could not open the WebSocket."));
    });

    socket.addEventListener("close", () => {
      if (!completed) {
        reject(new Error("The WebSocket closed before the response completed."));
      }
    });
  });
}

function autosizeTextarea() {
  elements.messageInput.style.height = "auto";
  elements.messageInput.style.height = `${Math.min(elements.messageInput.scrollHeight, 180)}px`;
}

async function init() {
  renderMessages();
  try {
    await loadHealth();
    await loadSessions();
  } catch (error) {
    setStatus(`Error: ${error.message}`, "error");
  }
}

elements.composer.addEventListener("submit", async (event) => {
  event.preventDefault();
  const content = elements.messageInput.value.trim();
  if (!content || state.busy) return;

  elements.messageInput.value = "";
  autosizeTextarea();
  await sendMessage(content);
});

elements.messageInput.addEventListener("input", autosizeTextarea);
elements.messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    elements.composer.requestSubmit();
  }
});

elements.providerSelect.addEventListener("change", updateModelOptions);
elements.ttsProviderSelect.addEventListener("change", updateVoiceOptions);
elements.newSessionButton.addEventListener("click", startNewSession);
elements.refreshButton.addEventListener("click", async () => {
  try {
    await loadHealth();
    await loadSessions();
    setStatus("Updated", "ready");
  } catch (error) {
    setStatus(`Error: ${error.message}`, "error");
  }
});

init();
