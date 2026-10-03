import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import * as ScrollArea from "@radix-ui/react-scroll-area";
import {
  BookOpen,
  Bot,
  Brain,
  Brush,
  Check,
  Database,
  FileText,
  ExternalLink,
  Globe,
  HardDrive,
  Heart,
  Image as ImageIcon,
  ImagePlus,
  Loader2,
  MessageSquare,
  MessageSquarePlus,
  Mic,
  Palette,
  Plus,
  Pencil,
  RefreshCw,
  Save,
  Search,
  Send,
  ServerCog,
  Settings,
  Shirt,
  ShoppingBag,
  Sparkles,
  SprayCan,
  Star,
  Trash2,
  UserRound,
  Volume2,
  X,
} from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  audioUrl,
  approveReflectionCandidate,
  ChatRequest,
  ChatStreamEvent,
  ChatToolImageResult,
  ChatToolOutfitItem,
  ChatToolProductResult,
  ChatToolQuestionnaireQuestion,
  ChatToolResultPayload,
  ChatToolWebResult,
  compareWardrobeImages,
  ContextPreviewResponse,
  createMemoryItem,
  createOutfitPlan,
  createProject,
  createStyleResearch,
  createSystemBackup,
  createWardrobeItem,
  deleteMemoryItem,
  deleteSession,
  deleteWardrobeItem,
  getContextPreview,
  getHealth,
  getMemoryItems,
  getMessages,
  getProfile,
  getProjects,
  getReflectionCandidates,
  getSemanticStatus,
  getSessions,
  getSystemLogTail,
  getSystemLogs,
  getSystemStatus,
  getWardrobeItems,
  getWebSocketUrl,
  indexSemanticMemory,
  MemoryItemResponse,
  MemoryKind,
  MessageResponse,
  OutputMode,
  ProfileResponse,
  ProfileUpdate,
  ReflectionCandidateResponse,
  rejectReflectionCandidate,
  runReflection,
  searchSemanticMemory,
  searchWeb,
  SemanticSearchResultResponse,
  SemanticStatusResponse,
  SystemBackupResponse,
  SystemLogFileResponse,
  SystemLogTailResponse,
  SystemStatusResponse,
  synthesizeSpeech,
  TextProviderName,
  TtsProviderName,
  updateWardrobeImage,
  updateMemoryItem,
  updateProfile,
  updateWardrobeItem,
  analyzeWardrobeImage,
  deleteWardrobeImage,
  extractWardrobeImage,
  getWardrobeImages,
  mediaUrl,
  uploadWardrobeImage,
  VisionProviderName,
  VisionProviderStatus,
  VisionCompareResponse,
  WardrobeExtractionDraft,
  WardrobeImageExtractResponse,
  WardrobeImageResponse,
  WardrobeItemCreate,
  WardrobeItemResponse,
  OutfitPlanResponse,
  StyleResearchResponse,
  WebSearchResultResponse,
} from "./lib/api";
import { cn } from "./lib/utils";

type StatusKind = "busy" | "ready" | "error";
type ViewMode = "chat" | "profile" | "wardrobe" | "memory" | "system";
type MemoryFilter = MemoryKind | "all";
type AccentTheme = "green" | "pink" | "purple" | "blue";
type ChatSectionId = "general" | "fashion" | "makeup" | "wardrobe" | "perfume" | "style";

const ACCENT_OPTIONS: Array<{ id: AccentTheme; label: string }> = [
  { id: "green", label: "Verde" },
  { id: "pink", label: "Rosa" },
  { id: "purple", label: "Morado" },
  { id: "blue", label: "Azul" },
];

const CHAT_SECTIONS: Array<{ id: ChatSectionId; label: string; title: string; placeholder: string }> = [
  { id: "general", label: "Chats", title: "New chat", placeholder: "Type something..." },
  { id: "fashion", label: "Moda", title: "Moda", placeholder: "Pregunta sobre outfits, siluetas o estilo..." },
  { id: "makeup", label: "Maquillaje", title: "Maquillaje", placeholder: "Pregunta sobre maquillaje, tonos o combinaciones..." },
  { id: "wardrobe", label: "Guardarropa", title: "Guardarropa", placeholder: "Describe una prenda o arma un look..." },
  { id: "perfume", label: "Perfumes", title: "Perfumes", placeholder: "Pregunta por fragancias o moods..." },
  { id: "style", label: "Estilo", title: "Estilo personal", placeholder: "Hablemos de tu estetica o referencias..." },
];

const WARDROBE_CATEGORIES = [
  "top",
  "bottom",
  "outerwear",
  "dress",
  "shoes",
  "accessory",
  "bag",
  "perfume",
  "makeup",
  "other",
];

interface MemoryEditorState {
  kind: MemoryKind;
  key: string;
  value: string;
  confidence: number;
}

interface MemoryFeedback {
  kind: "ready" | "error";
  text: string;
}

type ProfileDraft = Omit<ProfileResponse, "updated_at">;

interface WardrobeEditorState {
  name: string;
  category: string;
  subcategory: string;
  colors: string;
  material: string;
  brand: string;
  size_label: string;
  fit: string;
  season: string;
  occasions: string;
  style_tags: string;
  notes: string;
  favorite: boolean;
}

interface UiMessage extends Partial<MessageResponse> {
  client_id?: string;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
  tool_statuses?: string[];
  tool_results?: UiToolResult[];
}

interface UiToolResult {
  name: string;
  status: string;
  content: string;
  payload: ChatToolResultPayload;
}

const EMPTY_PROFILE: ProfileDraft = {
  display_name: "",
  gender_identity: "",
  age_range: "",
  city: "",
  height: "",
  body_notes: "",
  size_tops: "",
  size_bottoms: "",
  size_shoes: "",
  fit_preferences: "",
  favorite_colors: "",
  avoided_colors: "",
  style_keywords: "",
  primary_occasion: "",
  style_focus: "",
  comfort_notes: "",
  budget_notes: "",
  privacy_notes: "",
};

const EMPTY_WARDROBE_EDITOR: WardrobeEditorState = {
  name: "",
  category: "top",
  subcategory: "",
  colors: "",
  material: "",
  brand: "",
  size_label: "",
  fit: "",
  season: "",
  occasions: "",
  style_tags: "",
  notes: "",
  favorite: false,
};

function App() {
  const queryClient = useQueryClient();
  const [activeView, setActiveView] = useState<ViewMode>("chat");
  const [activeSection, setActiveSection] = useState<ChatSectionId>("general");
  const [accentTheme, setAccentTheme] = useState<AccentTheme>(() => readStoredAccentTheme());
  const [sessionSearch, setSessionSearch] = useState("");
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<UiMessage[]>([]);
  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [profileDraft, setProfileDraft] = useState<ProfileDraft>(EMPTY_PROFILE);
  const [wardrobeSearch, setWardrobeSearch] = useState("");
  const [wardrobeEditor, setWardrobeEditor] = useState<WardrobeEditorState>(EMPTY_WARDROBE_EDITOR);
  const [editingWardrobeId, setEditingWardrobeId] = useState<number | null>(null);
  const [status, setStatus] = useState<{ text: string; kind: StatusKind }>({
    text: "Connecting",
    kind: "busy",
  });
  const [textProvider, setTextProvider] = useState<TextProviderName | "">("");
  const [textModel, setTextModel] = useState("");
  const [ttsProvider, setTtsProvider] = useState<TtsProviderName | "">("");
  const [voice, setVoice] = useState("");
  const [visionProvider, setVisionProvider] = useState<VisionProviderName | "">("");
  const [visionModel, setVisionModel] = useState("");
  const [visionPrompt, setVisionPrompt] = useState("");
  const [visionComparison, setVisionComparison] = useState<VisionCompareResponse | null>(null);
  const [webSearchQuery, setWebSearchQuery] = useState("");
  const [webSearchResults, setWebSearchResults] = useState<WebSearchResultResponse[]>([]);
  const [styleResearch, setStyleResearch] = useState<StyleResearchResponse | null>(null);
  const [outfitPrompt, setOutfitPrompt] = useState("");
  const [outfitPlan, setOutfitPlan] = useState<OutfitPlanResponse | null>(null);
  const [wardrobeExtraction, setWardrobeExtraction] = useState<WardrobeImageExtractResponse | null>(null);
  const [outputMode, setOutputMode] = useState<OutputMode>("text");
  const [memoryFilter, setMemoryFilter] = useState<MemoryFilter>("all");
  const [editingMemoryId, setEditingMemoryId] = useState<number | null>(null);
  const [memoryFeedback, setMemoryFeedback] = useState<MemoryFeedback | null>(null);
  const [memorySaving, setMemorySaving] = useState(false);
  const [memoryEditor, setMemoryEditor] = useState<MemoryEditorState>({
    kind: "user_model",
    key: "",
    value: "",
    confidence: 0.8,
  });
  const [previewPrompt, setPreviewPrompt] = useState("What do you know about me?");
  const [contextPreview, setContextPreview] = useState<ContextPreviewResponse | null>(null);
  const [projectName, setProjectName] = useState("");
  const [projectActions, setProjectActions] = useState("");
  const [semanticQuery, setSemanticQuery] = useState("");
  const [semanticResults, setSemanticResults] = useState<SemanticSearchResultResponse[]>([]);
  const [semanticStatus, setSemanticStatus] = useState<SemanticStatusResponse | null>(null);
  const [selectedLogName, setSelectedLogName] = useState<string | null>(null);
  const [logTail, setLogTail] = useState<SystemLogTailResponse | null>(null);
  const [lastBackup, setLastBackup] = useState<SystemBackupResponse | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const sessionSearchRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    window.localStorage.setItem("mina.accentTheme", accentTheme);
    document.documentElement.dataset.minaTheme = accentTheme;
  }, [accentTheme]);

  const healthQuery = useQuery({ queryKey: ["health"], queryFn: getHealth });
  const systemStatusQuery = useQuery({ queryKey: ["system-status"], queryFn: getSystemStatus });
  const systemLogsQuery = useQuery({ queryKey: ["system-logs"], queryFn: getSystemLogs });
  const sessionsQuery = useQuery({ queryKey: ["sessions"], queryFn: getSessions });
  const profileQuery = useQuery({ queryKey: ["profile"], queryFn: getProfile });
  const wardrobeQuery = useQuery({ queryKey: ["wardrobe"], queryFn: () => getWardrobeItems() });
  const wardrobeImagesQuery = useQuery({ queryKey: ["wardrobe-images"], queryFn: () => getWardrobeImages() });
  const memoryQuery = useQuery({ queryKey: ["memory"], queryFn: () => getMemoryItems() });
  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: getProjects });
  const semanticStatusQuery = useQuery({ queryKey: ["semantic-status"], queryFn: getSemanticStatus });
  const reflectionCandidatesQuery = useQuery({
    queryKey: ["reflection-candidates"],
    queryFn: () => getReflectionCandidates("pending"),
  });
  const messageQuery = useQuery({
    queryKey: ["messages", currentSessionId],
    queryFn: () => getMessages(currentSessionId!),
    enabled: Boolean(currentSessionId),
  });

  const health = healthQuery.data;
  const systemStatus = systemStatusQuery.data;
  const systemLogs = systemLogsQuery.data ?? [];
  const sessions = sessionsQuery.data ?? [];
  const profile = profileQuery.data;
  const wardrobeItems = wardrobeQuery.data ?? [];
  const wardrobeImages = wardrobeImagesQuery.data ?? [];
  const memoryItems = memoryQuery.data ?? [];
  const projects = projectsQuery.data ?? [];
  const reflectionCandidates = reflectionCandidatesQuery.data ?? [];
  const activeSession = sessions.find((session) => session.id === currentSessionId);
  const activeTextProvider = health?.text_providers.find((provider) => provider.name === textProvider);
  const activeTtsProvider = health?.tts_providers.find((provider) => provider.name === ttsProvider);
  const activeVisionProvider = health?.vision_providers?.find((provider) => provider.name === visionProvider);
  const modelOptions = useMemo(() => activeTextProvider?.models ?? [], [activeTextProvider]);
  const voiceOptions = useMemo(() => activeTtsProvider?.voices ?? [], [activeTtsProvider]);
  const visionModelOptions = useMemo(() => activeVisionProvider?.models ?? [], [activeVisionProvider]);
  const filteredMemoryItems = useMemo(
    () => (memoryFilter === "all" ? memoryItems : memoryItems.filter((item) => item.kind === memoryFilter)),
    [memoryFilter, memoryItems],
  );

  useEffect(() => {
    if (semanticStatusQuery.data) setSemanticStatus(semanticStatusQuery.data);
  }, [semanticStatusQuery.data]);

  useEffect(() => {
    if (!selectedLogName && systemLogs.length > 0) {
      setSelectedLogName(systemLogs[0].name);
    }
  }, [selectedLogName, systemLogs]);

  useEffect(() => {
    if (!health) return;

    const nextText =
      health.text_providers.find((provider) => provider.name === health.text_provider && provider.available) ??
      health.text_providers.find((provider) => provider.available) ??
      health.text_providers[0];
    const nextTts =
      health.tts_providers.find((provider) => provider.name === health.tts_provider && provider.available) ??
      health.tts_providers.find((provider) => provider.available) ??
      health.tts_providers[0];
    const nextVision =
      health.vision_providers?.find((provider) => provider.name === health.vision_provider && provider.available) ??
      health.vision_providers?.find((provider) => provider.available) ??
      health.vision_providers?.[0];

    if (nextText && !textProvider) {
      setTextProvider(nextText.name);
      setTextModel(nextText.default_model);
    }
    if (nextTts && !ttsProvider) {
      setTtsProvider(nextTts.name);
      setVoice(nextTts.default_voice || nextTts.voices[0]?.id || "");
    }
    if (nextVision && !visionProvider) {
      setVisionProvider(nextVision.name);
      setVisionModel(nextVision.default_model);
    }
    setStatus({ text: "Ready", kind: "ready" });
  }, [health, textProvider, ttsProvider, visionProvider]);

  useEffect(() => {
    if (!messageQuery.data) return;
    setMessages((current) => {
      const hasOptimisticMessage = current.some((message) => message.client_id && !message.id);
      if (hasOptimisticMessage) return current;
      const currentById = new Map(current.filter((message) => message.id).map((message) => [message.id, message]));
      return messageQuery.data.map((message) => {
        const existing = currentById.get(message.id);
        return {
          ...message,
          tool_statuses: existing?.tool_statuses,
          tool_results: existing?.tool_results,
        };
      });
    });
  }, [messageQuery.data]);

  useEffect(() => {
    if (!profile) return;
    const { updated_at: _updatedAt, ...draft } = profile;
    setProfileDraft(draft);
  }, [profile]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  async function refreshAll() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["health"] }),
      queryClient.invalidateQueries({ queryKey: ["system-status"] }),
      queryClient.invalidateQueries({ queryKey: ["system-logs"] }),
      queryClient.invalidateQueries({ queryKey: ["sessions"] }),
      queryClient.invalidateQueries({ queryKey: ["profile"] }),
      queryClient.invalidateQueries({ queryKey: ["wardrobe"] }),
      queryClient.invalidateQueries({ queryKey: ["wardrobe-images"] }),
      queryClient.invalidateQueries({ queryKey: ["memory"] }),
      queryClient.invalidateQueries({ queryKey: ["projects"] }),
      queryClient.invalidateQueries({ queryKey: ["semantic-status"] }),
      queryClient.invalidateQueries({ queryKey: ["reflection-candidates"] }),
    ]);
  }

  function startNewSession() {
    setCurrentSessionId(null);
    setMessages([]);
    setPrompt("");
    setActiveView("chat");
  }

  async function removeSession(sessionId: string) {
    const session = sessions.find((item) => item.id === sessionId);
    const title = session?.title || "Untitled";
    if (!window.confirm(`Delete chat "${title}"?`)) return;

    setBusy(true);
    try {
      await deleteSession(sessionId);
      if (sessionId === currentSessionId) {
        setCurrentSessionId(null);
        setMessages([]);
        setPrompt("");
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["sessions"] }),
        queryClient.removeQueries({ queryKey: ["messages", sessionId] }),
      ]);
      setStatus({ text: "Chat deleted", kind: "ready" });
    } catch (error) {
      setStatus({ text: error instanceof Error ? error.message : "Delete chat error", kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  async function submitMessage(event: FormEvent) {
    event.preventDefault();
    const content = prompt.trim();
    await sendChatContent(content);
  }

  async function sendChatContent(content: string) {
    const trimmedContent = content.trim();
    if (!trimmedContent || busy) return;
    setPrompt("");
    setBusy(true);
    setStatus({ text: "Thinking", kind: "busy" });

    const userMessage: UiMessage = {
      client_id: crypto.randomUUID(),
      role: "user",
      content: trimmedContent,
      created_at: new Date().toISOString(),
    };
    const assistantMessage: UiMessage = {
      client_id: crypto.randomUUID(),
      role: "assistant",
      content: "",
      created_at: new Date().toISOString(),
      model: textProvider && textModel ? `${textProvider}/${textModel}` : textModel,
    };
    setMessages((current) => [...current, userMessage, assistantMessage]);

    try {
      await streamMessage(trimmedContent, assistantMessage.client_id!);
    } catch (error) {
      setMessages((current) => [
        ...current,
        {
          client_id: crypto.randomUUID(),
          role: "system",
          content: `Error: ${error instanceof Error ? error.message : String(error)}`,
          created_at: new Date().toISOString(),
        },
      ]);
      setStatus({ text: "Error", kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  async function streamMessage(content: string, assistantClientId: string) {
    await new Promise<void>((resolve, reject) => {
      const socket = new WebSocket(getWebSocketUrl());
      let completed = false;
      const toolStatuses: string[] = [];
      const toolResults: UiToolResult[] = [];

      socket.addEventListener("open", () => {
        const request: ChatRequest = {
          content,
          session_id: currentSessionId,
          input_mode: "text",
          output_mode: outputMode,
          provider: textProvider || null,
          model: textModel || null,
        };
        socket.send(JSON.stringify(request));
      });

      socket.addEventListener("message", (event) => {
        const payload = JSON.parse(event.data) as ChatStreamEvent;

        if (payload.type === "status") {
          setStatus({ text: "Thinking", kind: "busy" });
          return;
        }
        if (payload.type === "turn_started") {
          setCurrentSessionId(payload.session_id);
          setStatus({ text: "Generating", kind: "busy" });
          updateAssistant(assistantClientId, { model: `${payload.provider}/${payload.model}` });
          return;
        }
        if (payload.type === "tool_status") {
          const statusText = payload.status || "Working";
          toolStatuses.push(statusText);
          setStatus({ text: statusText, kind: "busy" });
          updateAssistant(assistantClientId, { tool_statuses: [...toolStatuses] });
          return;
        }
        if (payload.type === "tool_result") {
          const result: UiToolResult = {
            name: payload.name,
            status: payload.status,
            content: payload.content,
            payload: payload.payload,
          };
          toolResults.push(result);
          updateAssistant(assistantClientId, { tool_results: [...toolResults] });
          return;
        }
        if (payload.type === "assistant_chunk") {
          updateAssistantChunk(assistantClientId, payload.delta, `${payload.provider}/${payload.model}`);
          return;
        }
        if (payload.type === "assistant_message") {
          completed = true;
          socket.close();
          void finalizeAssistantMessage(payload, assistantClientId, {
            toolStatuses,
            toolResults,
          }).then(resolve).catch(reject);
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
        if (!completed) reject(new Error("The WebSocket closed before the response completed."));
      });
    });
  }

  async function finalizeAssistantMessage(
    payload: Extract<ChatStreamEvent, { type: "assistant_message" }>,
    assistantClientId: string,
    extras?: { toolStatuses: string[]; toolResults: UiToolResult[] },
  ) {
    const data = payload.data;
    setCurrentSessionId(data.session_id);
    updateAssistant(assistantClientId, {
      id: data.assistant_message_id,
      session_id: data.session_id,
      content: data.content,
      model: data.model,
      tokens: data.tokens_used,
    });

    let nextMessages = await getMessages(data.session_id);
    if (outputMode === "voice" || outputMode === "both") {
      setStatus({ text: "Synthesizing voice", kind: "busy" });
      const ttsResult = await synthesizeSpeech({
        text: data.content,
        message_id: data.assistant_message_id,
        provider: ttsProvider || null,
        voice: voice || null,
      });
      nextMessages = await getMessages(data.session_id);
      const audio = audioUrl(ttsResult.audio_url);
      if (audio) void new Audio(audio).play().catch(() => undefined);
    }

    const hydratedMessages = nextMessages.map((message) =>
      message.id === data.assistant_message_id
        ? {
            ...message,
            tool_statuses: extras?.toolStatuses ?? [],
            tool_results: extras?.toolResults ?? [],
          }
        : message,
    );
    setMessages(hydratedMessages);
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["sessions"] }),
      queryClient.invalidateQueries({ queryKey: ["messages", data.session_id] }),
      queryClient.invalidateQueries({ queryKey: ["memory"] }),
      queryClient.invalidateQueries({ queryKey: ["projects"] }),
      queryClient.invalidateQueries({ queryKey: ["reflection-candidates"] }),
    ]);
    setStatus({ text: "Ready", kind: "ready" });
  }

  function updateAssistant(clientId: string, patch: Partial<UiMessage>) {
    setMessages((current) =>
      current.map((message) => (message.client_id === clientId ? { ...message, ...patch } : message)),
    );
  }

  function updateAssistantChunk(clientId: string, delta: string, model: string) {
    setMessages((current) =>
      current.map((message) => {
        if (message.client_id !== clientId) return message;
        return { ...message, content: `${message.content}${delta}`, model };
      }),
    );
  }

  async function saveMemory(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    const validationError = memoryEditorError(memoryEditor, memoryItems, editingMemoryId);
    if (validationError) {
      setMemoryFeedback({ text: validationError, kind: "error" });
      return;
    }
    const draft = {
      ...memoryEditor,
      key: normalizeMemoryKey(memoryEditor.key) || `manual.${crypto.randomUUID()}`,
      value: memoryEditor.value.trim(),
    };
    setMemoryEditor(draft);
    setMemoryFeedback(null);
    setMemorySaving(true);
    setBusy(true);
    try {
      const saved = editingMemoryId !== null
        ? await updateMemoryItem(editingMemoryId, draft)
        : await createMemoryItem({ ...draft, source: "desktop", source_id: null });
      queryClient.setQueryData<MemoryItemResponse[]>(["memory"], (current = []) => [
        saved, ...current.filter((item) => item.id !== saved.id),
      ]);
      if (memoryFilter !== "all") setMemoryFilter(saved.kind);
      resetMemoryEditor(saved.kind);
      const feedback: MemoryFeedback = {
        text: editingMemoryId !== null ? "Changes saved." : "Memory saved.", kind: "ready",
      };
      setMemoryFeedback(feedback);
      setStatus(feedback);
      void refreshMemoryQueries();
    } catch (error) {
      const feedback: MemoryFeedback = {
        text: `${error instanceof Error ? error.message : "Could not save memory."} Your draft has been kept.`,
        kind: "error",
      };
      setMemoryFeedback(feedback);
      setStatus(feedback);
    } finally {
      setMemorySaving(false);
      setBusy(false);
    }
  }

  function editMemory(item: MemoryItemResponse) {
    setMemoryFeedback(null);
    setEditingMemoryId(item.id);
    setMemoryEditor({
      kind: item.kind,
      key: item.key,
      value: item.value,
      confidence: item.confidence,
    });
  }

  function resetMemoryEditor(kind: MemoryKind = memoryFilter === "all" ? "user_model" : memoryFilter) {
    setMemoryFeedback(null);
    setEditingMemoryId(null);
    setMemoryEditor({ kind, key: "", value: "", confidence: 0.8 });
  }

  async function removeMemory(itemId: number) {
    if (busy) return;
    setBusy(true);
    try {
      await deleteMemoryItem(itemId);
      queryClient.setQueryData<MemoryItemResponse[]>(["memory"], (current = []) => (
        current.filter((item) => item.id !== itemId)
      ));
      if (editingMemoryId === itemId) resetMemoryEditor();
      const feedback: MemoryFeedback = { text: "Memory deleted.", kind: "ready" };
      setMemoryFeedback(feedback);
      setStatus(feedback);
      void refreshMemoryQueries();
    } catch (error) {
      const feedback: MemoryFeedback = {
        text: error instanceof Error ? error.message : "Could not delete memory.", kind: "error",
      };
      setMemoryFeedback(feedback);
      setStatus(feedback);
    } finally {
      setBusy(false);
    }
  }

  async function saveProfile(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    try {
      const profile = await updateProfile(profileDraft as ProfileUpdate);
      const { updated_at: _updatedAt, ...draft } = profile;
      setProfileDraft(draft);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["profile"] }),
        queryClient.invalidateQueries({ queryKey: ["memory"] }),
      ]);
      setStatus({ text: "Profile saved", kind: "ready" });
    } catch (error) {
      setStatus({ text: error instanceof Error ? error.message : "Profile error", kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  async function applyStyleQuestionnaire(profilePatch: ProfileUpdate, promptSummary: string) {
    if (busy) return;
    setBusy(true);
    try {
      const profile = await updateProfile(profilePatch);
      const { updated_at: _updatedAt, ...draft } = profile;
      setProfileDraft(draft);
      setPrompt(promptSummary);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["profile"] }),
        queryClient.invalidateQueries({ queryKey: ["memory"] }),
        queryClient.invalidateQueries({ queryKey: ["semantic-status"] }),
      ]);
      setStatus({ text: "Style profile saved", kind: "ready" });
    } catch (error) {
      setStatus({ text: error instanceof Error ? error.message : "Profile error", kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  function editWardrobeItem(item: WardrobeItemResponse) {
    setEditingWardrobeId(item.id);
    setWardrobeEditor({
      name: item.name,
      category: item.category,
      subcategory: item.subcategory || "",
      colors: item.colors.join(", "),
      material: item.material || "",
      brand: item.brand || "",
      size_label: item.size_label || "",
      fit: item.fit || "",
      season: item.season || "",
      occasions: item.occasions.join(", "),
      style_tags: item.style_tags.join(", "),
      notes: item.notes || "",
      favorite: item.favorite,
    });
    setActiveView("wardrobe");
  }

  function resetWardrobeEditor() {
    setEditingWardrobeId(null);
    setWardrobeEditor(EMPTY_WARDROBE_EDITOR);
  }

  async function saveWardrobeItem(event: FormEvent) {
    event.preventDefault();
    if (busy || !wardrobeEditor.name.trim() || !wardrobeEditor.category.trim()) return;
    setBusy(true);
    try {
      const payload = wardrobePayload(wardrobeEditor);
      if (editingWardrobeId) {
        await updateWardrobeItem(editingWardrobeId, payload);
      } else {
        await createWardrobeItem(payload);
      }
      resetWardrobeEditor();
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["wardrobe"] }),
        queryClient.invalidateQueries({ queryKey: ["wardrobe-images"] }),
        queryClient.invalidateQueries({ queryKey: ["memory"] }),
      ]);
      setStatus({ text: "Wardrobe saved", kind: "ready" });
    } catch (error) {
      setStatus({ text: error instanceof Error ? error.message : "Wardrobe error", kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  async function removeWardrobeItem(itemId: number) {
    if (busy) return;
    if (!window.confirm("Delete this wardrobe item?")) return;
    setBusy(true);
    try {
      await deleteWardrobeItem(itemId);
      if (editingWardrobeId === itemId) resetWardrobeEditor();
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["wardrobe"] }),
        queryClient.invalidateQueries({ queryKey: ["wardrobe-images"] }),
        queryClient.invalidateQueries({ queryKey: ["memory"] }),
      ]);
      setStatus({ text: "Wardrobe item deleted", kind: "ready" });
    } catch (error) {
      setStatus({ text: error instanceof Error ? error.message : "Wardrobe error", kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  async function uploadWardrobeImageFile(file: File, itemId: string) {
    if (busy) return;
    setBusy(true);
    setStatus({ text: "Uploading image", kind: "busy" });
    try {
      const dataUrl = await readFileAsDataUrl(file);
      await uploadWardrobeImage({
        data_url: dataUrl,
        original_name: file.name || null,
        item_id: itemId ? Number(itemId) : null,
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["wardrobe"] }),
        queryClient.invalidateQueries({ queryKey: ["wardrobe-images"] }),
      ]);
      setStatus({ text: "Image uploaded", kind: "ready" });
    } catch (error) {
      setStatus({ text: error instanceof Error ? error.message : "Image upload error", kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  async function runWardrobeImageAnalysis(imageId: number) {
    if (busy) return;
    if (!visionProvider || (activeVisionProvider && !activeVisionProvider.available)) {
      setStatus({
        text: activeVisionProvider?.detail || "Vision provider is not ready",
        kind: "error",
      });
      return;
    }
    setBusy(true);
    setStatus({ text: "Analyzing image", kind: "busy" });
    try {
      await analyzeWardrobeImage({
        image_id: imageId,
        prompt: visionPrompt.trim() || null,
        provider: visionProvider || null,
        model: visionModel.trim() || null,
        save_memory: true,
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["wardrobe-images"] }),
        queryClient.invalidateQueries({ queryKey: ["memory"] }),
        queryClient.invalidateQueries({ queryKey: ["semantic-status"] }),
      ]);
      setStatus({ text: "Image analyzed", kind: "ready" });
    } catch (error) {
      setStatus({ text: error instanceof Error ? error.message : "Vision error", kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  async function compareWardrobeImageSelection(imageIds: number[]) {
    if (busy) return;
    if (imageIds.length < 2) {
      setStatus({ text: "Select at least two images to compare", kind: "error" });
      return;
    }
    if (!visionProvider || (activeVisionProvider && !activeVisionProvider.available)) {
      setStatus({
        text: activeVisionProvider?.detail || "Vision provider is not ready",
        kind: "error",
      });
      return;
    }
    setBusy(true);
    setStatus({ text: "Comparing images", kind: "busy" });
    try {
      const comparison = await compareWardrobeImages({
        image_ids: imageIds,
        prompt: visionPrompt.trim() || null,
        provider: visionProvider || null,
        model: visionModel.trim() || null,
        save_memory: true,
      });
      setVisionComparison(comparison);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["memory"] }),
        queryClient.invalidateQueries({ queryKey: ["semantic-status"] }),
      ]);
      setStatus({ text: "Images compared", kind: "ready" });
    } catch (error) {
      setStatus({ text: error instanceof Error ? error.message : "Vision comparison error", kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  async function runWardrobeImageExtraction(imageId: number) {
    if (busy) return;
    if (!visionProvider || (activeVisionProvider && !activeVisionProvider.available)) {
      setStatus({
        text: activeVisionProvider?.detail || "Vision provider is not ready",
        kind: "error",
      });
      return;
    }
    setBusy(true);
    setStatus({ text: "Extracting wardrobe item", kind: "busy" });
    try {
      const extraction = await extractWardrobeImage(imageId, {
        prompt: visionPrompt.trim() || null,
        provider: visionProvider || null,
        model: visionModel.trim() || null,
      });
      setWardrobeExtraction(extraction);
      setWardrobeEditor(draftToWardrobeEditor(extraction.draft));
      setEditingWardrobeId(null);
      await queryClient.invalidateQueries({ queryKey: ["wardrobe-images"] });
      setStatus({ text: "Extraction ready", kind: "ready" });
    } catch (error) {
      setStatus({ text: error instanceof Error ? error.message : "Extraction error", kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  async function saveWardrobeExtraction(draft: WardrobeExtractionDraft) {
    if (busy) return;
    setBusy(true);
    setStatus({ text: "Saving extracted item", kind: "busy" });
    try {
      const item = await createWardrobeItem(draftToWardrobePayload(draft));
      await updateWardrobeImage(draft.source_image_id, { item_id: item.id });
      setWardrobeExtraction(null);
      resetWardrobeEditor();
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["wardrobe"] }),
        queryClient.invalidateQueries({ queryKey: ["wardrobe-images"] }),
        queryClient.invalidateQueries({ queryKey: ["memory"] }),
      ]);
      setStatus({ text: "Extracted item saved", kind: "ready" });
    } catch (error) {
      setStatus({ text: error instanceof Error ? error.message : "Extraction save error", kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  function loadExtractionDraft(draft: WardrobeExtractionDraft) {
    setWardrobeEditor(draftToWardrobeEditor(draft));
    setEditingWardrobeId(null);
    setStatus({ text: "Draft loaded", kind: "ready" });
  }

  async function searchStyleWeb(event: FormEvent) {
    event.preventDefault();
    const query = webSearchQuery.trim();
    if (!query || busy) return;
    setBusy(true);
    setStatus({ text: "Searching web", kind: "busy" });
    try {
      const response = await searchWeb({ query, provider: null, limit: 6 });
      setWebSearchResults(response.results);
      setStatus({ text: `${response.results.length} web results`, kind: "ready" });
    } catch (error) {
      setStatus({ text: error instanceof Error ? error.message : "Web search error", kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  async function buildStyleResearchBrief() {
    const query = webSearchQuery.trim();
    if (!query || busy) return;
    setBusy(true);
    setStatus({ text: "Building research brief", kind: "busy" });
    try {
      const response = await createStyleResearch({
        query,
        search_provider: null,
        search_limit: 6,
        provider: textProvider || null,
        model: textModel.trim() || null,
      });
      setStyleResearch(response);
      setWebSearchResults(response.search.results);
      setStatus({ text: "Research brief ready", kind: "ready" });
    } catch (error) {
      setStatus({ text: error instanceof Error ? error.message : "Research error", kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  async function buildOutfitPlan(event: FormEvent) {
    event.preventDefault();
    const promptValue = outfitPrompt.trim();
    if (!promptValue || busy) return;
    setBusy(true);
    setStatus({ text: "Planning outfit", kind: "busy" });
    try {
      const response = await createOutfitPlan({
        prompt: promptValue,
        web_query: webSearchQuery.trim() || null,
        search_provider: null,
        search_limit: 6,
        provider: textProvider || null,
        model: textModel.trim() || null,
      });
      setOutfitPlan(response);
      if (response.search) setWebSearchResults(response.search.results);
      setStatus({ text: "Outfit plan ready", kind: "ready" });
    } catch (error) {
      setStatus({ text: error instanceof Error ? error.message : "Outfit plan error", kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  async function removeWardrobeImage(imageId: number) {
    if (busy) return;
    if (!window.confirm("Delete this image?")) return;
    setBusy(true);
    try {
      await deleteWardrobeImage(imageId);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["wardrobe"] }),
        queryClient.invalidateQueries({ queryKey: ["wardrobe-images"] }),
      ]);
      setStatus({ text: "Image deleted", kind: "ready" });
    } catch (error) {
      setStatus({ text: error instanceof Error ? error.message : "Image delete error", kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  async function refreshMemoryQueries() {
    setContextPreview(null);
    setSemanticResults([]);
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["memory"] }),
      queryClient.invalidateQueries({ queryKey: ["profile"] }),
      queryClient.invalidateQueries({ queryKey: ["wardrobe"] }),
      queryClient.invalidateQueries({ queryKey: ["wardrobe-images"] }),
      queryClient.invalidateQueries({ queryKey: ["projects"] }),
      queryClient.invalidateQueries({ queryKey: ["semantic-status"] }),
      queryClient.invalidateQueries({ queryKey: ["reflection-candidates"] }),
    ]);
  }

  async function previewContext() {
    if (busy) return;
    setBusy(true);
    try {
      const preview = await getContextPreview(currentSessionId, previewPrompt);
      setContextPreview(preview);
      setStatus({ text: "Context preview ready", kind: "ready" });
    } catch (error) {
      setStatus({ text: error instanceof Error ? error.message : "Context error", kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  async function submitProject(event: FormEvent) {
    event.preventDefault();
    const name = projectName.trim();
    if (!name || busy) return;
    setBusy(true);
    try {
      await createProject({
        name,
        status: "active",
        next_actions: projectActions
          .split("\n")
          .map((item) => item.trim())
          .filter(Boolean),
      });
      setProjectName("");
      setProjectActions("");
      await refreshMemoryQueries();
      setStatus({ text: "Project memory saved", kind: "ready" });
    } catch (error) {
      setStatus({ text: error instanceof Error ? error.message : "Project error", kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  async function indexSemantic() {
    if (busy) return;
    setBusy(true);
    try {
      const result = await indexSemanticMemory();
      await queryClient.invalidateQueries({ queryKey: ["semantic-status"] });
      setStatus({ text: `Indexed ${result.indexed} memories`, kind: "ready" });
    } catch (error) {
      setStatus({ text: error instanceof Error ? error.message : "Semantic index error", kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  async function semanticSearch(event: FormEvent) {
    event.preventDefault();
    const query = semanticQuery.trim();
    if (!query || busy) return;
    setBusy(true);
    try {
      const results = await searchSemanticMemory(query);
      setSemanticResults(results);
      setStatus({ text: `Semantic results: ${results.length}`, kind: "ready" });
    } catch (error) {
      setStatus({ text: error instanceof Error ? error.message : "Semantic search error", kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  async function reflectCurrentSession(event?: FormEvent) {
    event?.preventDefault();
    if (!currentSessionId) {
      setStatus({ text: "Open a chat before reflection", kind: "error" });
      return;
    }
    if (busy) return;
    setBusy(true);
    setStatus({ text: "Reflecting on current chat", kind: "busy" });
    try {
      const result = await runReflection({
        session_id: currentSessionId,
        provider: textProvider || null,
        model: textModel || null,
        limit: null,
      });
      await queryClient.invalidateQueries({ queryKey: ["reflection-candidates"] });
      setStatus({
        text: `Reflection: ${result.candidates.length} candidates, ${result.skipped} skipped`,
        kind: "ready",
      });
    } catch (error) {
      setStatus({ text: error instanceof Error ? error.message : "Reflection error", kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  async function approveReflection(candidateId: number) {
    if (busy) return;
    setBusy(true);
    try {
      await approveReflectionCandidate(candidateId);
      await refreshMemoryQueries();
      setStatus({ text: "Reflection approved", kind: "ready" });
    } catch (error) {
      setStatus({ text: error instanceof Error ? error.message : "Reflection error", kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  async function rejectReflection(candidateId: number) {
    if (busy) return;
    setBusy(true);
    try {
      await rejectReflectionCandidate(candidateId);
      await queryClient.invalidateQueries({ queryKey: ["reflection-candidates"] });
      setStatus({ text: "Reflection rejected", kind: "ready" });
    } catch (error) {
      setStatus({ text: error instanceof Error ? error.message : "Reflection error", kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  async function backupSystemDatabase() {
    if (busy) return;
    setBusy(true);
    setStatus({ text: "Creating database backup", kind: "busy" });
    try {
      const backup = await createSystemBackup();
      setLastBackup(backup);
      await queryClient.invalidateQueries({ queryKey: ["system-status"] });
      setStatus({ text: "Database backup created", kind: "ready" });
    } catch (error) {
      setStatus({ text: error instanceof Error ? error.message : "Backup error", kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  async function loadSystemLog(name: string) {
    setSelectedLogName(name);
    try {
      const tail = await getSystemLogTail(name, 240);
      setLogTail(tail);
      setStatus({ text: `Loaded ${name}`, kind: "ready" });
    } catch (error) {
      setLogTail(null);
      setStatus({ text: error instanceof Error ? error.message : "Log error", kind: "error" });
    }
  }

  const filteredSessions = useMemo(() => {
    const query = sessionSearch.trim().toLowerCase();
    if (!query) return sessions;
    return sessions.filter((session) => (session.title || "Untitled").toLowerCase().includes(query));
  }, [sessionSearch, sessions]);
  const filteredWardrobeItems = useMemo(() => {
    const query = wardrobeSearch.trim().toLowerCase();
    if (!query) return wardrobeItems;
    return wardrobeItems.filter((item) =>
      [
        item.name,
        item.category,
        item.subcategory,
        item.brand,
        item.material,
        item.fit,
        item.season,
        item.notes,
        ...item.colors,
        ...item.occasions,
        ...item.style_tags,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(query),
    );
  }, [wardrobeItems, wardrobeSearch]);
  const activeSectionMeta = CHAT_SECTIONS.find((section) => section.id === activeSection) ?? CHAT_SECTIONS[0];
  const sessionTitle = activeSession?.title || activeSectionMeta.title;
  const viewTitle =
    activeView === "profile"
      ? "About me"
      : activeView === "wardrobe"
        ? `Wardrobe (${wardrobeItems.length})`
        : activeView === "memory"
          ? "Memory & context"
          : activeView === "system"
            ? "System"
            : sessionTitle;

  return (
    <div
      className={cn("grid h-screen min-h-0 grid-rows-[28px_minmax(0,1fr)] bg-canvas text-ink", `theme-${accentTheme}`)}
      data-mina-theme={accentTheme}
    >
      <div className="drag-region flex items-center justify-between border-b border-line bg-panel px-3 text-[12px] text-muted">
        <div className="flex items-center gap-2">
          <Bot size={14} className="text-brand" />
          <span>Mina</span>
        </div>
        <div className="truncate pl-6 text-right">{status.text}</div>
      </div>

      <div className="grid min-h-0 grid-cols-[48px_minmax(236px,304px)_minmax(0,1fr)] max-[980px]:grid-cols-[48px_minmax(0,1fr)]">
        <aside className="flex min-h-0 flex-col items-center border-r border-line bg-sidebar py-2">
          <button
            className="mb-3 flex h-9 w-9 items-center justify-center rounded-lg text-brand hover:bg-hover"
            type="button"
            title="Mina"
            onClick={() => {
              setActiveView("chat");
              setActiveSection("general");
            }}
          >
            <Bot size={20} />
          </button>

          <nav className="flex flex-1 flex-col items-center gap-1">
            {CHAT_SECTIONS.map((section) => (
              <RailButton
                key={section.id}
                active={activeView === "chat" && activeSection === section.id}
                title={section.label}
                onClick={() => {
                  setActiveView("chat");
                  setActiveSection(section.id);
                }}
              >
                {sectionIcon(section.id)}
              </RailButton>
            ))}
          </nav>

          <div className="flex flex-col items-center gap-1 border-t border-line pt-2">
            <RailPaletteDots value={accentTheme} onChange={setAccentTheme} />
            <RailButton
              active={activeView === "profile"}
              title="Profile"
              onClick={() => setActiveView("profile")}
            >
              <UserRound size={17} />
            </RailButton>
            <RailButton
              active={activeView === "wardrobe"}
              title="Wardrobe"
              onClick={() => setActiveView("wardrobe")}
            >
              <ShoppingBag size={17} />
            </RailButton>
            <RailButton
              active={activeView === "memory"}
              title="Memory"
              onClick={() => setActiveView("memory")}
            >
              <Brain size={17} />
            </RailButton>
            <RailButton
              active={activeView === "system"}
              title="System"
              onClick={() => setActiveView("system")}
            >
              <Settings size={17} />
            </RailButton>
          </div>
        </aside>

        <aside className="grid min-h-0 grid-rows-[auto_auto_minmax(0,1fr)_auto] border-r border-line bg-panel max-[980px]:hidden">
          <div className="flex h-14 items-center justify-between px-4">
            <h2 className="truncate text-[18px] font-semibold text-ink">Chats ({sessions.length})</h2>
            <button
              className="flex h-8 items-center gap-1.5 rounded-md border border-brand/20 bg-brandSoft px-2.5 text-[12px] font-medium text-brandStrong hover:bg-hover"
              type="button"
              title="New chat"
              disabled={busy}
              onClick={startNewSession}
            >
              <Plus size={17} />
              New
            </button>
          </div>

          <div className="space-y-2 px-4 pb-3">
            <label className="flex h-9 items-center gap-2 rounded-md bg-field px-3 text-[12px] text-muted">
              <Search size={14} />
              <input
                ref={sessionSearchRef}
                className="min-w-0 flex-1 bg-transparent text-[12px] text-ink outline-none placeholder:text-muted"
                value={sessionSearch}
                placeholder="Search"
                onChange={(event) => setSessionSearch(event.target.value)}
              />
            </label>
            <button
              className="flex h-9 w-full items-center justify-center gap-2 rounded-md border border-line bg-panel text-[13px] font-medium text-ink hover:bg-hover disabled:opacity-60"
              type="button"
              disabled={busy}
              onClick={startNewSession}
            >
              <MessageSquarePlus size={15} />
              New chat
            </button>
          </div>

          <ScrollArea.Root className="min-h-0">
            <ScrollArea.Viewport className="h-full">
              <div className="space-y-1 px-3 pb-3">
                {filteredSessions.length === 0 ? (
                  <div className="rounded-md px-3 py-8 text-center text-[13px] text-muted">
                    No conversations.
                  </div>
                ) : (
                  filteredSessions.map((session) => {
                    const isActive = session.id === currentSessionId && activeView === "chat";
                    return (
                      <div
                        key={session.id}
                      className={cn(
                        "group grid w-full grid-cols-[minmax(0,1fr)_28px] items-center gap-1 overflow-hidden rounded-md",
                          isActive ? "bg-brandSoft text-brandStrong ring-1 ring-brand/20" : "text-sidebarInk hover:bg-hover",
                        )}
                      >
                        <button
                          className="min-w-0 px-3 py-2.5 text-left"
                          type="button"
                          onClick={() => {
                            setCurrentSessionId(session.id);
                            setActiveView("chat");
                          }}
                        >
                          <div className="flex min-w-0 items-center justify-between gap-3">
                            <div className="min-w-0 truncate text-[13px] font-medium">
                              {session.title || "Untitled"}
                            </div>
                            <span className={cn("shrink-0 text-[10px]", isActive ? "text-brandStrong/70" : "text-muted")}>
                              {relativeAge(session.updated_at)}
                            </span>
                          </div>
                          <div className={cn("mt-1 truncate text-[11px]", isActive ? "text-brandStrong/75" : "text-muted")}>
                            {session.message_count} messages
                          </div>
                        </button>
                        <button
                          className={cn(
                            "mr-1 flex h-7 w-7 items-center justify-center rounded-md",
                            isActive ? "text-brandStrong/70 hover:bg-white/60 hover:text-danger" : "text-muted hover:bg-hover hover:text-danger",
                          )}
                          type="button"
                          title="Delete chat"
                          aria-label="Delete chat"
                          disabled={busy}
                          onClick={() => void removeSession(session.id)}
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    );
                  })
                )}
              </div>
            </ScrollArea.Viewport>
            <ScrollArea.Scrollbar className="flex w-2 touch-none select-none bg-transparent p-0.5" orientation="vertical">
              <ScrollArea.Thumb className="relative flex-1 rounded-full bg-muted/35" />
            </ScrollArea.Scrollbar>
          </ScrollArea.Root>

          <div className="space-y-2 border-t border-line p-3">
            <div className="flex items-center gap-2 text-[12px] text-sidebarInk">
              <span className={cn("h-2 w-2 rounded-full", statusDot(status.kind))} />
              <span className="truncate">{status.text}</span>
            </div>
            <PaletteSwitch value={accentTheme} onChange={setAccentTheme} />
          </div>
        </aside>

        <main className="grid min-h-0 grid-rows-[auto_minmax(0,1fr)] bg-canvas">
          <header className="border-b border-line bg-panel px-5 py-3">
            <div className="flex min-h-8 items-center justify-between gap-4">
              <div className="min-w-0">
                <p className="text-[11px] font-semibold uppercase text-brand">
                  {activeView === "chat"
                    ? "Assistant chat"
                    : activeView === "profile"
                      ? "Personal profile"
                      : activeView === "wardrobe"
                        ? "Style inventory"
                        : activeView === "memory"
                          ? "Personal context"
                          : "Diagnostics"}
                </p>
                <h1 className="mt-0.5 truncate text-[18px] font-semibold text-ink">{viewTitle}</h1>
              </div>
              <div className="flex items-center gap-1 text-muted">
                <IconButton title="Refresh" disabled={busy} onClick={() => void refreshAll()}>
                  <RefreshCw size={14} />
                </IconButton>
                <IconButton title="Search chats" disabled={busy} onClick={() => sessionSearchRef.current?.focus()}>
                  <Search size={14} />
                </IconButton>
              </div>
            </div>

            {activeView === "chat" ? (
              <div className="mt-3 grid grid-cols-[repeat(auto-fit,minmax(132px,1fr))] gap-2">
                <HeaderSelect
                  label="Text provider"
                  value={textProvider}
                  disabled={busy}
                  onChange={(value) => {
                    const next = value as TextProviderName;
                    setTextProvider(next);
                    const provider = health?.text_providers.find((item) => item.name === next);
                    if (provider) setTextModel(provider.default_model);
                  }}
                >
                  {health?.text_providers.map((provider) => (
                    <option key={provider.name} value={provider.name}>
                      {provider.label}
                    </option>
                  ))}
                </HeaderSelect>

                <HeaderInput
                  label="Model"
                  value={textModel}
                  disabled={busy}
                  list="model-options"
                  onChange={setTextModel}
                />
                <datalist id="model-options">
                  {modelOptions.map((model) => (
                    <option key={model} value={model} />
                  ))}
                </datalist>

                <HeaderSelect
                  label="Voice provider"
                  value={ttsProvider}
                  disabled={busy}
                  onChange={(value) => {
                    const next = value as TtsProviderName;
                    setTtsProvider(next);
                    const provider = health?.tts_providers.find((item) => item.name === next);
                    setVoice(provider?.default_voice || provider?.voices[0]?.id || "");
                  }}
                >
                  {health?.tts_providers.map((provider) => (
                    <option key={provider.name} value={provider.name}>
                      {provider.label}
                    </option>
                  ))}
                </HeaderSelect>

                <HeaderSelect label="Voice" value={voice} disabled={busy} onChange={setVoice}>
                  {voiceOptions.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.label}
                    </option>
                  ))}
                </HeaderSelect>

                <HeaderSelect
                  label="Output"
                  value={outputMode}
                  disabled={busy}
                  onChange={(value) => setOutputMode(value as OutputMode)}
                >
                  <option value="text">Text</option>
                  <option value="voice">Voice</option>
                  <option value="both">Both</option>
                </HeaderSelect>
              </div>
            ) : null}
          </header>

          {activeView === "chat" ? (
            <ChatWorkspace
              busy={busy}
              section={activeSectionMeta}
              messages={messages}
              prompt={prompt}
              setPrompt={setPrompt}
              submitMessage={submitMessage}
              applyStyleQuestionnaire={(profilePatch, promptSummary) =>
                void applyStyleQuestionnaire(profilePatch, promptSummary)
              }
              submitToolPrompt={(content) => void sendChatContent(content)}
              messagesEndRef={messagesEndRef}
            />
          ) : activeView === "profile" ? (
            <ProfileWorkspace
              busy={busy}
              draft={profileDraft}
              updatedAt={profile?.updated_at ?? null}
              setDraft={setProfileDraft}
              saveProfile={saveProfile}
            />
          ) : activeView === "wardrobe" ? (
            <WardrobeWorkspace
              busy={busy}
              items={filteredWardrobeItems}
              allItems={wardrobeItems}
              images={wardrobeImages}
              totalCount={wardrobeItems.length}
              search={wardrobeSearch}
              setSearch={setWardrobeSearch}
              editor={wardrobeEditor}
              setEditor={setWardrobeEditor}
              editingId={editingWardrobeId}
              saveItem={saveWardrobeItem}
              editItem={editWardrobeItem}
              deleteItem={(itemId) => void removeWardrobeItem(itemId)}
              resetEditor={resetWardrobeEditor}
              uploadImage={(file, itemId) => void uploadWardrobeImageFile(file, itemId)}
              analyzeImage={(imageId) => void runWardrobeImageAnalysis(imageId)}
              extractImage={(imageId) => void runWardrobeImageExtraction(imageId)}
              compareImages={(imageIds) => void compareWardrobeImageSelection(imageIds)}
              deleteImage={(imageId) => void removeWardrobeImage(imageId)}
              visionProviders={health?.vision_providers ?? []}
              visionProvider={visionProvider}
              setVisionProvider={(provider) => {
                setVisionProvider(provider);
                const status = health?.vision_providers?.find((item) => item.name === provider);
                if (status) setVisionModel(status.default_model);
              }}
              visionModel={visionModel}
              setVisionModel={setVisionModel}
              visionModelOptions={visionModelOptions}
              visionPrompt={visionPrompt}
              setVisionPrompt={setVisionPrompt}
              activeVisionProvider={activeVisionProvider ?? null}
              comparison={visionComparison}
              extraction={wardrobeExtraction}
              loadExtraction={(draft) => loadExtractionDraft(draft)}
              saveExtraction={(draft) => void saveWardrobeExtraction(draft)}
              clearExtraction={() => setWardrobeExtraction(null)}
              webSearchQuery={webSearchQuery}
              setWebSearchQuery={setWebSearchQuery}
              webSearchResults={webSearchResults}
              searchWeb={searchStyleWeb}
              research={styleResearch}
              buildResearch={() => void buildStyleResearchBrief()}
              outfitPrompt={outfitPrompt}
              setOutfitPrompt={setOutfitPrompt}
              outfitPlan={outfitPlan}
              buildOutfitPlan={buildOutfitPlan}
            />
          ) : activeView === "memory" ? (
            <MemoryWorkspace
              busy={busy}
              items={filteredMemoryItems}
              allItems={memoryItems}
              projects={projects}
              filter={memoryFilter}
              setFilter={setMemoryFilter}
              editor={memoryEditor}
              setEditor={(value) => { setMemoryEditor(value); setMemoryFeedback(null); }}
              feedback={memoryFeedback}
              saving={memorySaving}
              loading={memoryQuery.isPending}
              loadError={memoryQuery.error?.message ?? null}
              reloadMemory={() => void memoryQuery.refetch()}
              editingId={editingMemoryId}
              editMemory={editMemory}
              resetEditor={() => resetMemoryEditor()}
              saveEditor={saveMemory}
              deleteMemory={(itemId) => void removeMemory(itemId)}
              previewPrompt={previewPrompt}
              setPreviewPrompt={setPreviewPrompt}
              contextPreview={contextPreview}
              previewContext={previewContext}
              projectName={projectName}
              setProjectName={setProjectName}
              projectActions={projectActions}
              setProjectActions={setProjectActions}
              submitProject={submitProject}
              currentSessionId={currentSessionId}
              reflectionCandidates={reflectionCandidates}
              reflectCurrentSession={reflectCurrentSession}
              approveReflection={(candidateId) => void approveReflection(candidateId)}
              rejectReflection={(candidateId) => void rejectReflection(candidateId)}
              semanticStatus={semanticStatus}
              indexSemantic={indexSemantic}
              semanticQuery={semanticQuery}
              setSemanticQuery={setSemanticQuery}
              semanticResults={semanticResults}
              semanticSearch={semanticSearch}
            />
          ) : (
            <SystemWorkspace
              busy={busy}
              status={systemStatus}
              logs={systemLogs}
              selectedLogName={selectedLogName}
              logTail={logTail}
              lastBackup={lastBackup}
              refreshSystem={() => void refreshAll()}
              backupDatabase={() => void backupSystemDatabase()}
              loadLog={(name) => void loadSystemLog(name)}
            />
          )}
        </main>
      </div>
    </div>
  );
}

function ChatWorkspace({
  busy,
  section,
  messages,
  prompt,
  setPrompt,
  submitMessage,
  applyStyleQuestionnaire,
  submitToolPrompt,
  messagesEndRef,
}: {
  busy: boolean;
  section: (typeof CHAT_SECTIONS)[number];
  messages: UiMessage[];
  prompt: string;
  setPrompt: (value: string) => void;
  submitMessage: (event: FormEvent) => void;
  applyStyleQuestionnaire: (profilePatch: ProfileUpdate, promptSummary: string) => void;
  submitToolPrompt: (content: string) => void;
  messagesEndRef: React.MutableRefObject<HTMLDivElement | null>;
}) {
  return (
    <section className="grid min-h-0 grid-rows-[minmax(0,1fr)_auto] bg-canvas">
      <ScrollArea.Root className="min-h-0 overflow-hidden">
        <ScrollArea.Viewport className="h-full">
          <div className="mx-auto flex min-h-full w-full max-w-4xl flex-col px-7 py-6">
            {messages.length === 0 ? (
              <div className="flex flex-1 items-center justify-center">
                <div className="max-w-xl text-center">
                  <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-brandSoft text-brand">
                    {sectionIcon(section.id)}
                  </div>
                  <h2 className="mt-5 text-[24px] font-semibold text-ink">{section.title}</h2>
                </div>
              </div>
            ) : (
              <div className="space-y-7">
                {messages.map((message, index) => (
                  <MessageBubble
                    key={message.id ?? message.client_id ?? index}
                    message={message}
                    applyStyleQuestionnaire={applyStyleQuestionnaire}
                    submitToolPrompt={submitToolPrompt}
                  />
                ))}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>
        </ScrollArea.Viewport>
        <ScrollArea.Scrollbar className="flex w-2 touch-none select-none bg-transparent p-0.5" orientation="vertical">
          <ScrollArea.Thumb className="relative flex-1 rounded-full bg-muted/35" />
        </ScrollArea.Scrollbar>
      </ScrollArea.Root>

      <form className="no-drag relative z-20 bg-canvas px-6 pb-5 pt-3" onSubmit={submitMessage}>
        <div className="no-drag mx-auto flex max-w-4xl items-end gap-2 rounded-lg border border-brand/15 bg-composer p-2 shadow-mina">
          <button
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-panel text-brandStrong"
            type="button"
            title="Voice"
          >
            <Mic size={16} />
          </button>
          <textarea
            className="no-drag max-h-40 min-h-10 min-w-0 flex-1 resize-none bg-transparent px-2 py-2 text-[14px] leading-6 text-brandStrong outline-none placeholder:text-brandStrong/55"
            value={prompt}
            placeholder={section.placeholder}
            onChange={(event) => setPrompt(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
          />
          <button
            className="flex h-9 w-9 items-center justify-center rounded-md text-brandStrong hover:bg-white/60 disabled:text-brandStrong/35"
            type="submit"
            disabled={busy || !prompt.trim()}
            title="Send"
          >
            {busy ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
          </button>
        </div>
      </form>
    </section>
  );
}

function ProfileWorkspace({
  busy,
  draft,
  updatedAt,
  setDraft,
  saveProfile,
}: {
  busy: boolean;
  draft: ProfileDraft;
  updatedAt: string | null;
  setDraft: (value: ProfileDraft) => void;
  saveProfile: (event: FormEvent) => void;
}) {
  const update = (field: keyof ProfileDraft, value: string) => setDraft({ ...draft, [field]: value });

  return (
    <ScrollArea.Root className="min-h-0 overflow-hidden bg-canvas">
      <ScrollArea.Viewport className="h-full">
        <form className="mx-auto grid w-full max-w-5xl gap-4 p-5" onSubmit={saveProfile}>
          <section className="rounded-lg border border-line bg-panel p-4">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2 text-[13px] font-medium text-ink">
                  <UserRound size={15} className="text-brand" />
                  <span>Quick profile</span>
                </div>
                <p className="mt-1 text-[12px] text-muted">
                  Confirmed facts Mina can use for style, fit and personal context.
                </p>
              </div>
              <button
                className="flex h-8 items-center gap-1.5 rounded-md bg-brand px-3 text-[12px] font-medium text-white hover:bg-brandStrong disabled:bg-muted/30 disabled:text-white/50"
                type="submit"
                disabled={busy}
              >
                <Save size={13} />
                Save profile
              </button>
            </div>

            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              <ProfileInput label="Preferred name" value={draft.display_name} onChange={(value) => update("display_name", value)} />
              <ProfileInput label="Style gender identity" value={draft.gender_identity} onChange={(value) => update("gender_identity", value)} />
              <ProfileInput label="Age range" value={draft.age_range} onChange={(value) => update("age_range", value)} />
              <ProfileInput label="City / climate" value={draft.city} onChange={(value) => update("city", value)} />
              <ProfileInput label="Height" value={draft.height} onChange={(value) => update("height", value)} />
              <ProfileInput label="Top size" value={draft.size_tops} onChange={(value) => update("size_tops", value)} />
              <ProfileInput label="Bottom size" value={draft.size_bottoms} onChange={(value) => update("size_bottoms", value)} />
              <ProfileInput label="Shoe size" value={draft.size_shoes} onChange={(value) => update("size_shoes", value)} />
            </div>

            <div className="mt-3 grid gap-3 lg:grid-cols-2">
              <ProfileArea label="Body / proportion notes" value={draft.body_notes} onChange={(value) => update("body_notes", value)} />
              <ProfileArea label="Fit preferences" value={draft.fit_preferences} onChange={(value) => update("fit_preferences", value)} />
            </div>
          </section>

          <section className="rounded-lg border border-line bg-panel p-4">
            <div className="mb-4 flex items-center gap-2 text-[13px] font-medium text-ink">
              <Shirt size={15} className="text-brand" />
              <span>Style model</span>
            </div>
            <div className="grid gap-3 lg:grid-cols-2">
              <ProfileArea label="Style keywords" value={draft.style_keywords} onChange={(value) => update("style_keywords", value)} />
              <ProfileArea label="Comfort constraints" value={draft.comfort_notes} onChange={(value) => update("comfort_notes", value)} />
              <ProfileInput label="Primary occasion" value={draft.primary_occasion} onChange={(value) => update("primary_occasion", value)} />
              <ProfileInput label="Style focus" value={draft.style_focus} onChange={(value) => update("style_focus", value)} />
              <ProfileInput label="Favorite colors" value={draft.favorite_colors} onChange={(value) => update("favorite_colors", value)} />
              <ProfileInput label="Avoided colors" value={draft.avoided_colors} onChange={(value) => update("avoided_colors", value)} />
              <ProfileArea label="Budget / brand notes" value={draft.budget_notes} onChange={(value) => update("budget_notes", value)} />
              <ProfileArea label="Image and web privacy notes" value={draft.privacy_notes} onChange={(value) => update("privacy_notes", value)} />
            </div>
            <div className="mt-3 text-[11px] text-muted">
              {updatedAt ? `Last updated ${formatDateTime(updatedAt)}` : "No profile saved yet."}
            </div>
          </section>
        </form>
      </ScrollArea.Viewport>
      <ScrollArea.Scrollbar className="flex w-2 touch-none select-none bg-transparent p-0.5" orientation="vertical">
        <ScrollArea.Thumb className="relative flex-1 rounded-full bg-muted/35" />
      </ScrollArea.Scrollbar>
    </ScrollArea.Root>
  );
}

function WardrobeWorkspace({
  busy,
  items,
  allItems,
  images,
  totalCount,
  search,
  setSearch,
  editor,
  setEditor,
  editingId,
  saveItem,
  editItem,
  deleteItem,
  resetEditor,
  uploadImage,
  analyzeImage,
  extractImage,
  compareImages,
  deleteImage,
  visionProviders,
  visionProvider,
  setVisionProvider,
  visionModel,
  setVisionModel,
  visionModelOptions,
  visionPrompt,
  setVisionPrompt,
  activeVisionProvider,
  comparison,
  extraction,
  loadExtraction,
  saveExtraction,
  clearExtraction,
  webSearchQuery,
  setWebSearchQuery,
  webSearchResults,
  searchWeb,
  research,
  buildResearch,
  outfitPrompt,
  setOutfitPrompt,
  outfitPlan,
  buildOutfitPlan,
}: {
  busy: boolean;
  items: WardrobeItemResponse[];
  allItems: WardrobeItemResponse[];
  images: WardrobeImageResponse[];
  totalCount: number;
  search: string;
  setSearch: (value: string) => void;
  editor: WardrobeEditorState;
  setEditor: (value: WardrobeEditorState) => void;
  editingId: number | null;
  saveItem: (event: FormEvent) => void;
  editItem: (item: WardrobeItemResponse) => void;
  deleteItem: (itemId: number) => void;
  resetEditor: () => void;
  uploadImage: (file: File, itemId: string) => void;
  analyzeImage: (imageId: number) => void;
  extractImage: (imageId: number) => void;
  compareImages: (imageIds: number[]) => void;
  deleteImage: (imageId: number) => void;
  visionProviders: VisionProviderStatus[];
  visionProvider: VisionProviderName | "";
  setVisionProvider: (provider: VisionProviderName) => void;
  visionModel: string;
  setVisionModel: (value: string) => void;
  visionModelOptions: string[];
  visionPrompt: string;
  setVisionPrompt: (value: string) => void;
  activeVisionProvider: VisionProviderStatus | null;
  comparison: VisionCompareResponse | null;
  extraction: WardrobeImageExtractResponse | null;
  loadExtraction: (draft: WardrobeExtractionDraft) => void;
  saveExtraction: (draft: WardrobeExtractionDraft) => void;
  clearExtraction: () => void;
  webSearchQuery: string;
  setWebSearchQuery: (value: string) => void;
  webSearchResults: WebSearchResultResponse[];
  searchWeb: (event: FormEvent) => void;
  research: StyleResearchResponse | null;
  buildResearch: () => void;
  outfitPrompt: string;
  setOutfitPrompt: (value: string) => void;
  outfitPlan: OutfitPlanResponse | null;
  buildOutfitPlan: (event: FormEvent) => void;
}) {
  const [uploadItemId, setUploadItemId] = useState("");
  const [compareImageIds, setCompareImageIds] = useState<number[]>([]);
  const itemById = useMemo(() => new Map(allItems.map((item) => [item.id, item])), [allItems]);
  const update = (field: keyof WardrobeEditorState, value: string | boolean) =>
    setEditor({ ...editor, [field]: value });

  useEffect(() => {
    const validIds = new Set(images.map((image) => image.id));
    setCompareImageIds((current) => current.filter((imageId) => validIds.has(imageId)));
  }, [images]);

  function toggleCompareImage(imageId: number) {
    setCompareImageIds((current) =>
      current.includes(imageId)
        ? current.filter((item) => item !== imageId)
        : [...current, imageId].slice(-6),
    );
  }

  return (
    <div className="grid min-h-0 grid-cols-1 gap-4 overflow-auto bg-canvas p-4 lg:grid-cols-[320px_minmax(0,1fr)] lg:overflow-hidden">
      <form className="min-h-0 overflow-auto rounded-lg border border-line bg-panel p-4 lg:max-h-full" onSubmit={saveItem}>
        <div className="mb-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-[13px] font-medium text-ink">
            <ShoppingBag size={15} className="text-brand" />
            <span>{editingId ? "Edit item" : "Add item"}</span>
          </div>
          {editingId ? (
            <button
              className="h-8 rounded-md px-2 text-[12px] text-muted hover:bg-hover hover:text-ink"
              type="button"
              disabled={busy}
              onClick={resetEditor}
            >
              Cancel
            </button>
          ) : null}
        </div>

        <div className="space-y-2">
          <WardrobeInput label="Name" value={editor.name} onChange={(value) => update("name", value)} />
          <label className="block">
            <div className="mb-1 text-[11px] text-sidebarInk">Category</div>
            <input
              className="h-8 w-full rounded-md border border-line bg-field px-2 text-[12px] text-ink outline-none"
              value={editor.category}
              list="wardrobe-categories"
              disabled={busy}
              onChange={(event) => update("category", event.target.value)}
            />
            <datalist id="wardrobe-categories">
              {WARDROBE_CATEGORIES.map((category) => (
                <option key={category} value={category} />
              ))}
            </datalist>
          </label>
          <div className="grid grid-cols-2 gap-2">
            <WardrobeInput label="Subtype" value={editor.subcategory} onChange={(value) => update("subcategory", value)} />
            <WardrobeInput label="Brand" value={editor.brand} onChange={(value) => update("brand", value)} />
            <WardrobeInput label="Size" value={editor.size_label} onChange={(value) => update("size_label", value)} />
            <WardrobeInput label="Fit" value={editor.fit} onChange={(value) => update("fit", value)} />
            <WardrobeInput label="Material" value={editor.material} onChange={(value) => update("material", value)} />
            <WardrobeInput label="Season" value={editor.season} onChange={(value) => update("season", value)} />
          </div>
          <WardrobeInput label="Colors" value={editor.colors} placeholder="black, cream, denim" onChange={(value) => update("colors", value)} />
          <WardrobeInput label="Occasions" value={editor.occasions} placeholder="work, night, casual" onChange={(value) => update("occasions", value)} />
          <WardrobeInput label="Style tags" value={editor.style_tags} placeholder="minimal, korean, elegant" onChange={(value) => update("style_tags", value)} />
          <label className="block">
            <div className="mb-1 text-[11px] text-sidebarInk">Notes</div>
            <textarea
              className="min-h-20 w-full rounded-md border border-line bg-field px-2 py-2 text-[12px] leading-5 text-ink outline-none placeholder:text-muted"
              value={editor.notes}
              disabled={busy}
              placeholder="How it fits, when it works, what to avoid..."
              onChange={(event) => update("notes", event.target.value)}
            />
          </label>
          <label className="flex items-center gap-2 text-[12px] text-sidebarInk">
            <input
              className="accent-brand"
              type="checkbox"
              checked={editor.favorite}
              disabled={busy}
              onChange={(event) => update("favorite", event.target.checked)}
            />
            Favorite
          </label>
          <button
            className="flex h-8 items-center gap-1.5 rounded-md bg-brand px-3 text-[12px] font-medium text-white hover:bg-brandStrong disabled:bg-muted/30 disabled:text-white/50"
            type="submit"
            disabled={busy || !editor.name.trim() || !editor.category.trim()}
          >
            <Save size={13} />
            {editingId ? "Update item" : "Save item"}
          </button>
        </div>
      </form>

      <div className="min-h-0 space-y-4 overflow-auto pr-1">
      {extraction ? (
        <section className="rounded-lg border border-brand/20 bg-brandSoft/55 p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-[13px] font-semibold text-ink">
                <Sparkles size={15} className="text-brand" />
                <span>Extracted item draft</span>
                <span className="text-[11px] font-normal text-muted">
                  {extraction.provider}/{extraction.model} · confidence {Math.round(extraction.draft.confidence * 100)}%
                </span>
              </div>
              <div className="mt-2 text-[13px] font-medium text-ink">{extraction.draft.name}</div>
              <div className="mt-1 text-[12px] text-sidebarInk">
                {extraction.draft.category}
                {extraction.draft.subcategory ? ` · ${extraction.draft.subcategory}` : ""}
                {extraction.draft.colors.length ? ` · ${extraction.draft.colors.join(", ")}` : ""}
              </div>
              {extraction.draft.notes ? (
                <p className="mt-2 max-w-3xl text-[12px] leading-5 text-sidebarInk">{extraction.draft.notes}</p>
              ) : null}
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              <button
                className="flex h-8 items-center gap-1.5 rounded-md border border-brand/20 bg-panel px-3 text-[12px] font-medium text-brandStrong hover:bg-hover disabled:opacity-45"
                type="button"
                disabled={busy}
                onClick={() => loadExtraction(extraction.draft)}
              >
                <Pencil size={13} />
                Load form
              </button>
              <button
                className="flex h-8 items-center gap-1.5 rounded-md bg-brand px-3 text-[12px] font-medium text-white hover:bg-brandStrong disabled:opacity-45"
                type="button"
                disabled={busy}
                onClick={() => saveExtraction(extraction.draft)}
              >
                <Save size={13} />
                Save item
              </button>
              <IconButton title="Dismiss" disabled={busy} onClick={clearExtraction}>
                <X size={13} />
              </IconButton>
            </div>
          </div>
        </section>
      ) : null}
      <section className="rounded-lg border border-line bg-panel">
        <div className="border-b border-line p-4">
          <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-2 text-[13px] font-medium text-ink">
                <Shirt size={15} className="text-brand" />
                <span>Wardrobe inventory</span>
              </div>
              <div className="mt-1 text-[12px] text-muted">{items.length} visible · {totalCount} saved</div>
            </div>
            <label className="flex h-8 w-full items-center gap-2 rounded-md bg-field px-3 text-[12px] text-muted sm:w-[220px]">
              <Search size={14} />
              <input
                className="min-w-0 flex-1 bg-transparent text-[12px] text-ink outline-none placeholder:text-muted"
                value={search}
                placeholder="Search wardrobe"
                onChange={(event) => setSearch(event.target.value)}
              />
            </label>
          </div>
        </div>

        <div className="max-h-[280px] overflow-auto">
            <div className="grid gap-3 p-4 md:grid-cols-2 2xl:grid-cols-3">
              {items.length === 0 ? (
                <div className="rounded-md px-3 py-8 text-center text-[13px] text-muted md:col-span-2 2xl:col-span-3">
                  No wardrobe items yet.
                </div>
              ) : (
                items.map((item) => (
                  <article key={item.id} className="rounded-lg border border-line bg-field p-3">
                    <div className="mb-2 flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5">
                          {item.favorite ? <Star size={13} className="fill-brand text-brand" /> : null}
                          <h3 className="truncate text-[13px] font-semibold text-ink">{item.name}</h3>
                        </div>
                        <div className="mt-1 text-[11px] text-muted">
                          {item.category}{item.subcategory ? ` · ${item.subcategory}` : ""} · {relativeAge(item.updated_at)}
                        </div>
                      </div>
                      <div className="flex shrink-0 gap-1">
                        <IconButton title="Edit" disabled={busy} onClick={() => editItem(item)}>
                          <Pencil size={13} />
                        </IconButton>
                        <IconButton title="Delete" disabled={busy} onClick={() => deleteItem(item.id)}>
                          <Trash2 size={13} />
                        </IconButton>
                      </div>
                    </div>
                    <div className="space-y-1 text-[12px] leading-5 text-sidebarInk">
                      <InfoRow label="Color" value={item.colors.join(", ") || "-"} />
                      <InfoRow label="Fit" value={item.fit || "-"} />
                      <InfoRow label="Size" value={item.size_label || "-"} />
                      <InfoRow label="Brand" value={item.brand || "-"} />
                    </div>
                    {item.style_tags.length ? (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {item.style_tags.map((tag) => (
                          <span key={tag} className="rounded-full bg-brandSoft px-2 py-0.5 text-[11px] text-brandStrong">
                            {tag}
                          </span>
                        ))}
                      </div>
                    ) : null}
                    {item.notes ? <p className="mt-2 text-[12px] leading-5 text-sidebarInk">{item.notes}</p> : null}
                    <div className="mt-2 text-[11px] text-muted">
                      {item.image_count ? `${item.image_count} images` : "No images yet"}
                    </div>
                  </article>
                ))
              )}
            </div>
        </div>
      </section>

      <section className="rounded-lg border border-line bg-panel">
        <div className="border-b border-line p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2 text-[13px] font-medium text-ink">
                <ImageIcon size={15} className="text-brand" />
                <span>Image gallery</span>
              </div>
              <div className="mt-1 text-[12px] text-muted">
                {images.length} saved · analyze outfits, garments and references
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <select
                className="h-8 max-w-[220px] rounded-md border border-line bg-field px-2 text-[12px] text-ink outline-none"
                value={uploadItemId}
                disabled={busy}
                onChange={(event) => setUploadItemId(event.target.value)}
              >
                <option value="">No linked item</option>
                {allItems.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
              <label className="flex h-8 cursor-pointer items-center gap-1.5 rounded-md bg-brand px-3 text-[12px] font-medium text-white hover:bg-brandStrong">
                <ImagePlus size={14} />
                Upload
                <input
                  className="hidden"
                  type="file"
                  accept="image/*"
                  disabled={busy}
                  onChange={(event) => {
                    const file = event.currentTarget.files?.[0];
                    if (file) uploadImage(file, uploadItemId);
                    event.currentTarget.value = "";
                  }}
                />
              </label>
              <button
                className="flex h-8 items-center gap-1.5 rounded-md bg-brandSoft px-3 text-[12px] font-medium text-brandStrong hover:bg-brand/15 disabled:opacity-45"
                type="button"
                disabled={busy || compareImageIds.length < 2 || Boolean(activeVisionProvider && !activeVisionProvider.available)}
                onClick={() => compareImages(compareImageIds)}
              >
                <Sparkles size={14} />
                Compare {compareImageIds.length ? `(${compareImageIds.length})` : ""}
              </button>
            </div>
          </div>

          <div className="mt-4 grid gap-2 lg:grid-cols-[150px_180px_minmax(0,1fr)]">
            <label className="block">
              <div className="mb-1 text-[11px] text-sidebarInk">Vision provider</div>
              <select
                className="h-8 w-full rounded-md border border-line bg-field px-2 text-[12px] text-ink outline-none"
                value={visionProvider}
                disabled={busy || visionProviders.length === 0}
                onChange={(event) => setVisionProvider(event.target.value as VisionProviderName)}
              >
                {visionProviders.length === 0 ? (
                  <option value="">No providers</option>
                ) : (
                  visionProviders.map((provider) => (
                    <option key={provider.name} value={provider.name}>
                      {provider.label}{provider.available ? "" : " (not ready)"}
                    </option>
                  ))
                )}
              </select>
            </label>
            <label className="block">
              <div className="mb-1 text-[11px] text-sidebarInk">Vision model</div>
              <input
                className="h-8 w-full rounded-md border border-line bg-field px-2 text-[12px] text-ink outline-none placeholder:text-muted"
                value={visionModel}
                list="vision-model-options"
                disabled={busy}
                placeholder="xiaomi/mimo-v2.5"
                onChange={(event) => setVisionModel(event.target.value)}
              />
              <datalist id="vision-model-options">
                {visionModelOptions.map((model) => (
                  <option key={model} value={model} />
                ))}
              </datalist>
            </label>
            <WardrobeInput
              label="Analysis prompt"
              value={visionPrompt}
              placeholder="Optional. Example: analyze this for winter outfits in Temuco"
              onChange={setVisionPrompt}
            />
          </div>
          {activeVisionProvider?.detail ? (
            <div className="mt-2 text-[12px] text-muted">{activeVisionProvider.detail}</div>
          ) : null}
          {comparison ? (
            <div className="mt-4 rounded-lg border border-line bg-field p-3">
              <div className="mb-2 flex items-center gap-2 text-[12px] font-semibold text-ink">
                <Sparkles size={14} className="text-brand" />
                <span>Visual comparison</span>
                <span className="text-[11px] font-normal text-muted">
                  {comparison.provider}/{comparison.model}
                </span>
              </div>
              <MarkdownContent content={comparison.analysis} />
            </div>
          ) : null}
        </div>

        <div className="min-h-[320px] max-h-[560px] overflow-auto">
            <div className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-3">
              {images.length === 0 ? (
                <div className="rounded-md px-3 py-8 text-center text-[13px] text-muted md:col-span-2 xl:col-span-3 2xl:col-span-4">
                  No images yet.
                </div>
              ) : (
                images.map((image) => {
                  const linkedItem = image.item_id ? itemById.get(image.item_id) : null;
                  const src = mediaUrl(image.thumbnail_url || image.image_url);
                  return (
                    <article key={image.id} className="overflow-hidden rounded-lg border border-line bg-field">
                      <div className="aspect-[4/3] bg-panel">
                        {src ? (
                          <img className="h-full w-full object-cover" src={src} alt={image.original_name || "Wardrobe image"} />
                        ) : (
                          <div className="flex h-full items-center justify-center text-muted">
                            <ImageIcon size={22} />
                          </div>
                        )}
                      </div>
                      <div className="space-y-3 p-3">
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <h3 className="truncate text-[13px] font-semibold text-ink">
                              {linkedItem?.name || image.original_name || `Image ${image.id}`}
                            </h3>
                            <div className="mt-1 text-[11px] text-muted">
                              {image.width && image.height ? `${image.width}x${image.height} · ` : ""}
                              {relativeAge(image.created_at)}
                            </div>
                          </div>
                          <div className="flex shrink-0 gap-1">
                            <button
                              className="flex h-7 items-center gap-1 rounded-md bg-brandSoft px-2 text-[11px] font-medium text-brandStrong hover:bg-brand/15 disabled:opacity-45"
                              type="button"
                              title="Analyze"
                              aria-label="Analyze"
                              disabled={busy || !visionProvider || Boolean(activeVisionProvider && !activeVisionProvider.available)}
                              onClick={() => analyzeImage(image.id)}
                            >
                              <Sparkles size={13} />
                              <span>Analyze</span>
                            </button>
                            <button
                              className="flex h-7 items-center gap-1 rounded-md border border-brand/20 bg-panel px-2 text-[11px] font-medium text-brandStrong hover:bg-hover disabled:opacity-45"
                              type="button"
                              title="Extract item"
                              aria-label="Extract item"
                              disabled={busy || !visionProvider || Boolean(activeVisionProvider && !activeVisionProvider.available)}
                              onClick={() => extractImage(image.id)}
                            >
                              <ShoppingBag size={13} />
                              <span>Extract</span>
                            </button>
                            <IconButton title="Delete" disabled={busy} onClick={() => deleteImage(image.id)}>
                              <Trash2 size={13} />
                            </IconButton>
                          </div>
                        </div>
                        {linkedItem ? (
                          <span className="inline-flex rounded-full bg-brandSoft px-2 py-0.5 text-[11px] text-brandStrong">
                            {linkedItem.category}
                          </span>
                        ) : null}
                        <label className="flex items-center gap-2 text-[12px] text-sidebarInk">
                          <input
                            className="accent-brand"
                            type="checkbox"
                            checked={compareImageIds.includes(image.id)}
                            disabled={busy}
                            onChange={() => toggleCompareImage(image.id)}
                          />
                          Compare
                        </label>
                        {image.analysis ? (
                          <div className="max-h-48 overflow-auto rounded-md border border-line bg-panel px-3 py-2">
                            <MarkdownContent content={image.analysis} />
                          </div>
                        ) : (
                          <p className="text-[12px] leading-5 text-muted">
                            Not analyzed yet.
                          </p>
                        )}
                      </div>
                    </article>
                  );
                })
              )}
            </div>
        </div>
      </section>
      <section className="rounded-lg border border-line bg-panel">
        <div className="border-b border-line p-4">
          <div className="flex items-center gap-2 text-[13px] font-medium text-ink">
            <Globe size={15} className="text-brand" />
            <span>Web research</span>
          </div>
          <form className="mt-3 flex flex-col gap-2 sm:flex-row" onSubmit={searchWeb}>
            <label className="flex h-8 min-w-0 flex-1 items-center gap-2 rounded-md bg-field px-3 text-[12px] text-muted">
              <Search size={14} />
              <input
                className="min-w-0 flex-1 bg-transparent text-[12px] text-ink outline-none placeholder:text-muted"
                value={webSearchQuery}
                placeholder="Search outfit references, trends, products..."
                disabled={busy}
                onChange={(event) => setWebSearchQuery(event.target.value)}
              />
            </label>
            <button
              className="flex h-8 items-center justify-center gap-1.5 rounded-md bg-brand px-3 text-[12px] font-medium text-white hover:bg-brandStrong disabled:opacity-45"
              type="submit"
              disabled={busy || !webSearchQuery.trim()}
            >
              <Search size={14} />
              Search
            </button>
            <button
              className="flex h-8 items-center justify-center gap-1.5 rounded-md border border-brand/20 bg-panel px-3 text-[12px] font-medium text-brandStrong hover:bg-hover disabled:opacity-45"
              type="button"
              disabled={busy || !webSearchQuery.trim()}
              onClick={buildResearch}
            >
              <FileText size={14} />
              Brief
            </button>
          </form>
        </div>
        <div className="grid gap-2 p-4">
          {research ? (
            <div className="rounded-lg border border-brand/20 bg-brandSoft/45 p-3">
              <div className="mb-2 flex flex-wrap items-center gap-2 text-[12px] font-semibold text-ink">
                <FileText size={14} className="text-brand" />
                <span>Research brief</span>
                <span className="text-[11px] font-normal text-muted">
                  {research.provider}/{research.model}
                </span>
              </div>
              <MarkdownContent content={research.brief} />
            </div>
          ) : null}
          <form className="rounded-lg border border-line bg-field p-3" onSubmit={buildOutfitPlan}>
            <div className="mb-2 flex items-center gap-2 text-[12px] font-semibold text-ink">
              <Shirt size={14} className="text-brand" />
              <span>Outfit planner</span>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <input
                className="h-8 min-w-0 flex-1 rounded-md border border-line bg-panel px-3 text-[12px] text-ink outline-none placeholder:text-muted"
                value={outfitPrompt}
                placeholder="Example: outfit for rain in Temuco using my boots"
                disabled={busy}
                onChange={(event) => setOutfitPrompt(event.target.value)}
              />
              <button
                className="flex h-8 items-center justify-center gap-1.5 rounded-md bg-brand px-3 text-[12px] font-medium text-white hover:bg-brandStrong disabled:opacity-45"
                type="submit"
                disabled={busy || !outfitPrompt.trim()}
              >
                <Sparkles size={14} />
                Plan
              </button>
            </div>
            {outfitPlan ? (
              <div className="mt-3 rounded-md border border-line bg-panel p-3">
                <div className="mb-2 flex flex-wrap items-center gap-2 text-[12px] font-semibold text-ink">
                  <Sparkles size={14} className="text-brand" />
                  <span>Plan</span>
                  <span className="text-[11px] font-normal text-muted">
                    {outfitPlan.provider}/{outfitPlan.model}
                  </span>
                </div>
                <MarkdownContent content={outfitPlan.plan} />
              </div>
            ) : null}
          </form>
          {webSearchResults.length === 0 ? (
            <div className="rounded-md px-3 py-6 text-center text-[13px] text-muted">
              No web results yet.
            </div>
          ) : (
            webSearchResults.map((result) => (
              <a
                key={result.url}
                className="block rounded-lg border border-line bg-field p-3 hover:border-brand/25 hover:bg-hover"
                href={result.url}
                target="_blank"
                rel="noreferrer"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate text-[13px] font-semibold text-ink">{result.title}</div>
                    <div className="mt-1 truncate text-[11px] text-muted">{result.url}</div>
                  </div>
                  <ExternalLink size={14} className="shrink-0 text-muted" />
                </div>
                {result.snippet ? (
                  <p className="mt-2 text-[12px] leading-5 text-sidebarInk">{result.snippet}</p>
                ) : null}
              </a>
            ))
          )}
        </div>
      </section>
      </div>
    </div>
  );
}

function ProfileInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <div className="mb-1 text-[11px] text-sidebarInk">{label}</div>
      <input
        className="h-8 w-full rounded-md border border-line bg-field px-2 text-[12px] text-ink outline-none placeholder:text-muted"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function ProfileArea({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <div className="mb-1 text-[11px] text-sidebarInk">{label}</div>
      <textarea
        className="min-h-20 w-full rounded-md border border-line bg-field px-2 py-2 text-[12px] leading-5 text-ink outline-none placeholder:text-muted"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function WardrobeInput({
  label,
  value,
  placeholder,
  onChange,
}: {
  label: string;
  value: string;
  placeholder?: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <div className="mb-1 text-[11px] text-sidebarInk">{label}</div>
      <input
        className="h-8 w-full rounded-md border border-line bg-field px-2 text-[12px] text-ink outline-none placeholder:text-muted"
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function MemoryWorkspace({
  busy,
  items,
  allItems,
  projects,
  filter,
  setFilter,
  editor,
  setEditor,
  feedback,
  saving,
  loading,
  loadError,
  reloadMemory,
  editingId,
  editMemory,
  resetEditor,
  saveEditor,
  deleteMemory,
  previewPrompt,
  setPreviewPrompt,
  contextPreview,
  previewContext,
  projectName,
  setProjectName,
  projectActions,
  setProjectActions,
  submitProject,
  currentSessionId,
  reflectionCandidates,
  reflectCurrentSession,
  approveReflection,
  rejectReflection,
  semanticStatus,
  indexSemantic,
  semanticQuery,
  setSemanticQuery,
  semanticResults,
  semanticSearch,
}: {
  busy: boolean;
  items: MemoryItemResponse[];
  allItems: MemoryItemResponse[];
  projects: MemoryItemResponse[];
  filter: MemoryFilter;
  setFilter: (value: MemoryFilter) => void;
  editor: MemoryEditorState;
  setEditor: (value: MemoryEditorState) => void;
  feedback: MemoryFeedback | null;
  saving: boolean;
  loading: boolean;
  loadError: string | null;
  reloadMemory: () => void;
  editingId: number | null;
  editMemory: (item: MemoryItemResponse) => void;
  resetEditor: () => void;
  saveEditor: (event: FormEvent) => void;
  deleteMemory: (itemId: number) => void;
  previewPrompt: string;
  setPreviewPrompt: (value: string) => void;
  contextPreview: ContextPreviewResponse | null;
  previewContext: () => void;
  projectName: string;
  setProjectName: (value: string) => void;
  projectActions: string;
  setProjectActions: (value: string) => void;
  submitProject: (event: FormEvent) => void;
  currentSessionId: string | null;
  reflectionCandidates: ReflectionCandidateResponse[];
  reflectCurrentSession: (event?: FormEvent) => void;
  approveReflection: (candidateId: number) => void;
  rejectReflection: (candidateId: number) => void;
  semanticStatus: SemanticStatusResponse | null;
  indexSemantic: () => void;
  semanticQuery: string;
  setSemanticQuery: (value: string) => void;
  semanticResults: SemanticSearchResultResponse[];
  semanticSearch: (event: FormEvent) => void;
}) {
  const editorRef = useRef<HTMLFormElement>(null);
  const valueRef = useRef<HTMLTextAreaElement>(null);
  const validationError = memoryEditorError(editor, allItems, editingId);
  useEffect(() => {
    if (editingId === null) return;
    editorRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    valueRef.current?.focus({ preventScroll: true });
  }, [editingId]);
  return (
    <div className="grid min-h-0 grid-cols-1 gap-4 overflow-auto p-4 xl:grid-cols-[minmax(320px,0.9fr)_minmax(0,1.1fr)]">
      <section className="grid min-h-[560px] min-w-0 grid-rows-[auto_minmax(200px,1fr)] rounded-lg border border-line bg-panel">
        <div className="border-b border-line p-3">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-[13px] font-medium text-ink">
              <Brain size={15} className="text-brand" />
              <span>Stable memory</span>
              <span className="text-[11px] text-muted">{items.length}</span>
            </div>
            <IconButton title="Refresh memory" disabled={busy || loading} onClick={reloadMemory}>
              <RefreshCw size={13} />
            </IconButton>
            <select
              className="h-8 rounded-md border border-line bg-field px-2 text-[12px] text-ink outline-none"
              value={filter}
              aria-label="Filter memories by category"
              disabled={busy}
              onChange={(event) => setFilter(event.target.value as MemoryFilter)}
            >
              <option value="all">All</option>
              <option value="user_model">User</option>
              <option value="project_model">Projects</option>
              <option value="episodic_event">Episodes</option>
              <option value="relationship_signal">Style</option>
              <option value="personality_profile">Personality</option>
              <option value="self_model">Self</option>
              <option value="fashion_preference">Fashion</option>
              <option value="wardrobe_model">Wardrobe</option>
              <option value="style_reference">References</option>
              <option value="media_memory">Media</option>
            </select>
          </div>

          <form ref={editorRef} className="space-y-3" onSubmit={saveEditor}>
            <div className="flex items-center justify-between gap-2">
              <div>
                <h3 className="text-[13px] font-medium text-ink">
                  {editingId !== null ? "Edit memory" : "New memory"}
                </h3>
                <p className="mt-1 text-[11px] text-muted">
                  {editingId !== null ? "Update the selected memory below." : "Write what Mina should remember. A key can be created automatically."}
                </p>
              </div>
            </div>
            <div className="grid grid-cols-[152px_minmax(0,1fr)] gap-2">
              <label className="space-y-1 text-[11px] text-muted">
                <span>Category</span>
              <select
                aria-label="Memory category"
                className="h-8 w-full rounded-md border border-line bg-field px-2 text-[12px] text-ink outline-none"
                value={editor.kind}
                disabled={busy}
                onChange={(event) => setEditor({ ...editor, kind: event.target.value as MemoryKind })}
              >
                <option value="user_model">User</option>
                <option value="project_model">Project</option>
                <option value="episodic_event">Episode</option>
                <option value="relationship_signal">Style</option>
                <option value="personality_profile">Personality</option>
                <option value="self_model">Self</option>
                <option value="fashion_preference">Fashion</option>
                <option value="wardrobe_model">Wardrobe</option>
                <option value="style_reference">Reference</option>
                <option value="media_memory">Media</option>
              </select>
              </label>
              <label className="min-w-0 space-y-1 text-[11px] text-muted">
                <span>{editingId !== null ? "Key" : "Key (optional)"}</span>
              <input
                aria-label="Memory key"
                maxLength={160}
                required={editingId !== null}
                className="h-8 w-full min-w-0 rounded-md border border-line bg-field px-2 text-[12px] text-ink outline-none placeholder:text-muted"
                value={editor.key}
                disabled={busy}
                placeholder="Created automatically if empty"
                onChange={(event) => setEditor({ ...editor, key: event.target.value })}
              />
              </label>
            </div>
            <label className="block space-y-1 text-[11px] text-muted">
              <span>What should Mina remember?</span>
            <textarea
              ref={valueRef}
              aria-label="Memory content"
              required
              maxLength={4000}
              className="min-h-32 w-full resize-y rounded-md border border-line bg-field px-3 py-2 text-[13px] leading-5 text-ink outline-none placeholder:text-muted focus:border-brand"
              value={editor.value}
              disabled={busy}
              placeholder="For example: I prefer relaxed silhouettes and neutral colors."
              onChange={(event) => setEditor({ ...editor, value: event.target.value })}
            />
              <span className="block text-right">{editor.value.length} / 4000</span>
            </label>
            {validationError && editor.value.trim() ? (
              <p className="text-[12px] text-red-600">{validationError}</p>
            ) : null}
            {feedback ? (
              <div
                role={feedback.kind === "error" ? "alert" : "status"}
                className={cn("rounded-md border px-3 py-2 text-[12px]", feedback.kind === "error"
                  ? "border-red-200 bg-red-50 text-red-700" : "border-brand/25 bg-active text-ink")}
              >
                {feedback.text}
              </div>
            ) : null}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <label className="flex items-center gap-2 text-[12px] text-muted">
                Confidence
                <input
                  className="w-28 accent-brand"
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={editor.confidence}
                  disabled={busy}
                  onChange={(event) => setEditor({ ...editor, confidence: Number(event.target.value) })}
                />
                <span>{editor.confidence.toFixed(2)}</span>
              </label>
              <div className="flex gap-2">
                {editingId ? (
                  <button
                    className="h-8 rounded-md px-2 text-[12px] text-muted hover:bg-hover hover:text-ink"
                    type="button"
                    disabled={busy}
                    onClick={resetEditor}
                  >
                    Cancel
                  </button>
                ) : null}
                <button
                  className="flex h-8 items-center gap-1.5 rounded-md bg-brand px-3 text-[12px] font-medium text-white hover:bg-brandStrong disabled:bg-muted/30 disabled:text-white/50"
                  type="submit"
                  disabled={busy || Boolean(validationError)}
                >
                  {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
                  {saving ? "Saving…" : editingId !== null ? "Save changes" : "Save memory"}
                </button>
              </div>
            </div>
          </form>
        </div>

        <ScrollArea.Root className="min-h-0">
          <ScrollArea.Viewport className="h-full">
            <div className="space-y-2 p-3">
              {loadError ? (
                <div role="alert" className="rounded-md border border-red-200 bg-red-50 p-3 text-[12px] text-red-700">
                  <p>Could not load memory: {loadError}</p>
                  <button type="button" className="mt-2 underline" onClick={reloadMemory}>Try again</button>
                </div>
              ) : loading ? (
                <p className="py-8 text-center text-[13px] text-muted">Loading memory…</p>
              ) : items.length === 0 ? (
                <div className="rounded-md px-3 py-8 text-center text-[13px] text-muted">
                  {filter === "all" ? "No memories yet. Add your first memory above." : "No memories in this category."}
                </div>
              ) : (
                items.map((item) => (
                  <div key={item.id} className={cn("rounded-md border p-3", editingId === item.id
                    ? "border-brand bg-active ring-1 ring-brand/20" : "border-line bg-field")}>
                    <div className="mb-2 flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <div className="break-words text-[13px] font-medium text-ink" title={item.key}>
                          {item.key.startsWith("manual.") ? item.value.split("\n")[0].slice(0, 100) : item.key}
                        </div>
                        <div className="mt-1 text-[11px] text-muted">
                          {memoryKindLabel(item.kind)} · {item.confidence.toFixed(2)} · {relativeAge(item.updated_at)}
                        </div>
                      </div>
                      <div className="flex shrink-0 gap-1">
                        {editingId === item.id ? <span className="mr-1 self-center text-[11px] text-brand">Editing</span> : null}
                        <IconButton title="Edit" disabled={busy} onClick={() => editMemory(item)}>
                          <Pencil size={13} />
                        </IconButton>
                        <IconButton title="Delete" disabled={busy} onClick={() => deleteMemory(item.id)}>
                          <Trash2 size={13} />
                        </IconButton>
                      </div>
                    </div>
                    <p className="whitespace-pre-wrap break-words text-[12px] leading-5 text-sidebarInk">{item.value}</p>
                  </div>
                ))
              )}
            </div>
          </ScrollArea.Viewport>
          <ScrollArea.Scrollbar className="flex w-2 touch-none select-none bg-transparent p-0.5" orientation="vertical">
            <ScrollArea.Thumb className="relative flex-1 rounded-full bg-muted/35" />
          </ScrollArea.Scrollbar>
        </ScrollArea.Root>
      </section>

      <div className="grid min-h-0 grid-rows-[minmax(0,1fr)_minmax(0,1fr)] gap-4">
        <section className="grid min-h-0 grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="grid min-h-0 grid-rows-[auto_minmax(0,1fr)] rounded-lg border border-line bg-panel">
            <div className="border-b border-line p-3">
              <div className="mb-3 flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-[13px] font-medium text-ink">
                  <Sparkles size={15} className="text-brand" />
                  <span>Reflection</span>
                </div>
                <button
                  className="flex h-8 items-center gap-1.5 rounded-md bg-brand px-3 text-[12px] font-medium text-white hover:bg-brandStrong disabled:bg-muted/30 disabled:text-white/50"
                  type="button"
                  disabled={busy || !currentSessionId}
                  onClick={() => reflectCurrentSession()}
                >
                  Ask Mina
                </button>
              </div>
              <p className="text-[12px] leading-5 text-muted">
                Mina reviews the current chat and proposes memories. You decide what becomes stable.
              </p>
            </div>
            <ScrollArea.Root className="min-h-0">
              <ScrollArea.Viewport className="h-full">
                <div className="space-y-2 p-3">
                  {reflectionCandidates.length === 0 ? (
                    <div className="rounded-md px-3 py-8 text-center text-[13px] text-muted">
                      {currentSessionId ? "No pending candidates." : "Open a chat to reflect on it."}
                    </div>
                  ) : (
                    reflectionCandidates.map((candidate) => (
                      <div key={candidate.id} className="rounded-md border border-line bg-field p-3">
                        <div className="mb-2 flex items-center justify-between gap-2">
                          <div className="min-w-0">
                            <div className="truncate text-[12px] font-medium text-ink">{candidate.key}</div>
                            <div className="mt-1 text-[11px] text-muted">
                              {memoryKindLabel(candidate.kind)} · {candidate.confidence.toFixed(2)}
                            </div>
                          </div>
                          <div className="flex gap-1">
                            <IconButton title="Approve" disabled={busy} onClick={() => approveReflection(candidate.id)}>
                              <Check size={13} />
                            </IconButton>
                            <IconButton title="Reject" disabled={busy} onClick={() => rejectReflection(candidate.id)}>
                              <X size={13} />
                            </IconButton>
                          </div>
                        </div>
                        <p className="text-[12px] leading-5 text-sidebarInk">{candidate.value}</p>
                        {candidate.evidence ? (
                          <p className="mt-2 text-[11px] leading-4 text-muted">{candidate.evidence}</p>
                        ) : null}
                      </div>
                    ))
                  )}
                </div>
              </ScrollArea.Viewport>
              <ScrollArea.Scrollbar className="flex w-2 touch-none select-none bg-transparent p-0.5" orientation="vertical">
                <ScrollArea.Thumb className="relative flex-1 rounded-full bg-muted/35" />
              </ScrollArea.Scrollbar>
            </ScrollArea.Root>
          </div>

          <div className="grid min-h-0 grid-rows-[auto_minmax(0,1fr)] rounded-lg border border-line bg-panel">
            <form className="border-b border-line p-3" onSubmit={submitProject}>
              <div className="mb-3 flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-[13px] font-medium text-ink">
                  <FileText size={15} className="text-brand" />
                  <span>Projects</span>
                </div>
                <span className="text-[12px] text-muted">{projects.length}</span>
              </div>
              <input
                className="h-8 w-full rounded-md border border-line bg-field px-2 text-[12px] text-ink outline-none placeholder:text-muted"
                value={projectName}
                disabled={busy}
                placeholder="Project name"
                onChange={(event) => setProjectName(event.target.value)}
              />
              <textarea
                className="mt-2 min-h-16 w-full rounded-md border border-line bg-field px-2 py-2 text-[12px] leading-5 text-ink outline-none placeholder:text-muted"
                value={projectActions}
                disabled={busy}
                placeholder="Next actions, one per line"
                onChange={(event) => setProjectActions(event.target.value)}
              />
              <button
                className="mt-2 flex h-8 items-center gap-1.5 rounded-md bg-brand px-3 text-[12px] font-medium text-white hover:bg-brandStrong disabled:bg-muted/30 disabled:text-white/50"
                type="submit"
                disabled={busy || !projectName.trim()}
              >
                <Save size={13} />
                Save project
              </button>
            </form>
            <ScrollArea.Root className="min-h-0">
              <ScrollArea.Viewport className="h-full">
                <div className="space-y-2 p-3">
                  {projects.length === 0 ? (
                    <div className="rounded-md px-3 py-8 text-center text-[13px] text-muted">
                      No project memories.
                    </div>
                  ) : (
                    projects.map((project) => (
                      <div key={project.id} className="rounded-md border border-line bg-field p-3">
                        <div className="truncate text-[12px] font-medium text-ink">{project.key}</div>
                        <p className="mt-2 whitespace-pre-wrap text-[12px] leading-5 text-sidebarInk">
                          {projectSummary(project)}
                        </p>
                      </div>
                    ))
                  )}
                </div>
              </ScrollArea.Viewport>
              <ScrollArea.Scrollbar className="flex w-2 touch-none select-none bg-transparent p-0.5" orientation="vertical">
                <ScrollArea.Thumb className="relative flex-1 rounded-full bg-muted/35" />
              </ScrollArea.Scrollbar>
            </ScrollArea.Root>
          </div>
        </section>

        <section className="grid min-h-0 grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="grid min-h-0 grid-rows-[auto_minmax(0,1fr)] rounded-lg border border-line bg-panel">
            <div className="border-b border-line p-3">
              <div className="mb-3 flex items-center gap-2 text-[13px] font-medium text-ink">
                <Bot size={15} className="text-brand" />
                <span>Context preview</span>
              </div>
              <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-2">
                <input
                  className="h-8 min-w-0 flex-1 rounded-md border border-line bg-field px-2 text-[12px] text-ink outline-none placeholder:text-muted"
                  value={previewPrompt}
                  disabled={busy}
                  placeholder="Prompt to preview"
                  onChange={(event) => setPreviewPrompt(event.target.value)}
                />
                <button
                  className="flex h-8 items-center gap-1.5 rounded-md bg-brand px-3 text-[12px] font-medium text-white hover:bg-brandStrong"
                  type="button"
                  disabled={busy || !previewPrompt.trim()}
                  onClick={previewContext}
                >
                  Preview
                </button>
              </div>
            </div>
            <ScrollArea.Root className="min-h-0">
              <ScrollArea.Viewport className="h-full">
                <div className="space-y-3 p-3 text-[12px] text-sidebarInk">
                  {contextPreview ? (
                    <>
                      <InfoRow label="Intent" value={contextPreview.intent} />
                      <InfoRow label="Memories" value={String(contextPreview.memory_items.length)} />
                      <InfoRow label="Semantic" value={String(contextPreview.semantic_items.length)} />
                      <pre className="max-h-56 overflow-auto whitespace-pre-wrap rounded-md border border-line bg-field p-3 font-mono text-[11px] leading-5">
                        {contextPreview.system_context}
                      </pre>
                    </>
                  ) : (
                    <div className="rounded-md px-3 py-8 text-center text-[13px] text-muted">
                      Preview the context Mina would send to the model.
                    </div>
                  )}
                </div>
              </ScrollArea.Viewport>
              <ScrollArea.Scrollbar className="flex w-2 touch-none select-none bg-transparent p-0.5" orientation="vertical">
                <ScrollArea.Thumb className="relative flex-1 rounded-full bg-muted/35" />
              </ScrollArea.Scrollbar>
            </ScrollArea.Root>
          </div>

          <div className="grid min-h-0 grid-rows-[auto_minmax(0,1fr)] rounded-lg border border-line bg-panel">
            <form className="border-b border-line p-3" onSubmit={semanticSearch}>
              <div className="mb-3 flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-[13px] font-medium text-ink">
                  <Search size={15} className="text-brand" />
                  <span>Semantic memory</span>
                </div>
                <button
                  className="h-7 rounded-md px-2 text-[12px] text-muted hover:bg-hover hover:text-ink"
                  type="button"
                  disabled={busy}
                  onClick={indexSemantic}
                >
                  Index
                </button>
              </div>
              <div className="mb-2 text-[11px] text-muted">
                {semanticStatus
                  ? semanticStatus.available
                    ? `Ready · ${semanticStatus.collection}`
                    : semanticStatus.detail || "Unavailable"
                  : "Checking"}
              </div>
              <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-2">
                <input
                  className="h-8 min-w-0 flex-1 rounded-md border border-line bg-field px-2 text-[12px] text-ink outline-none placeholder:text-muted"
                  value={semanticQuery}
                  disabled={busy}
                  placeholder="Search memories by meaning"
                  onChange={(event) => setSemanticQuery(event.target.value)}
                />
                <button
                  className="flex h-8 items-center gap-1.5 rounded-md bg-brand px-3 text-[12px] font-medium text-white hover:bg-brandStrong"
                  type="submit"
                  disabled={busy || !semanticQuery.trim()}
                >
                  Search
                </button>
              </div>
            </form>
            <ScrollArea.Root className="min-h-0">
              <ScrollArea.Viewport className="h-full">
                <div className="space-y-2 p-3">
                  {semanticResults.length === 0 ? (
                    <div className="rounded-md px-3 py-8 text-center text-[13px] text-muted">
                      No semantic results.
                    </div>
                  ) : (
                    semanticResults.map((result, index) => (
                      <div key={`${result.memory_item?.id ?? index}`} className="rounded-md border border-line bg-field p-3">
                        <div className="flex items-center justify-between gap-2 text-[11px] text-muted">
                          <span>{result.memory_item?.key ?? "Unknown memory"}</span>
                          <span>{result.score.toFixed(3)}</span>
                        </div>
                        <p className="mt-2 text-[12px] leading-5 text-sidebarInk">
                          {result.memory_item?.value ?? String(result.payload.text ?? "")}
                        </p>
                      </div>
                    ))
                  )}
                </div>
              </ScrollArea.Viewport>
              <ScrollArea.Scrollbar className="flex w-2 touch-none select-none bg-transparent p-0.5" orientation="vertical">
                <ScrollArea.Thumb className="relative flex-1 rounded-full bg-muted/35" />
              </ScrollArea.Scrollbar>
            </ScrollArea.Root>
          </div>
        </section>
      </div>
    </div>
  );
}

function SystemWorkspace({
  busy,
  status,
  logs,
  selectedLogName,
  logTail,
  lastBackup,
  refreshSystem,
  backupDatabase,
  loadLog,
}: {
  busy: boolean;
  status: SystemStatusResponse | undefined;
  logs: SystemLogFileResponse[];
  selectedLogName: string | null;
  logTail: SystemLogTailResponse | null;
  lastBackup: SystemBackupResponse | null;
  refreshSystem: () => void;
  backupDatabase: () => void;
  loadLog: (name: string) => void;
}) {
  const counts = Object.entries(status?.counts ?? {});
  const configured = Object.entries(status?.configured ?? {});

  return (
    <div className="grid min-h-0 grid-cols-1 gap-4 overflow-auto p-4 xl:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
      <div className="grid min-h-0 grid-rows-[auto_minmax(0,1fr)] gap-4">
        <section className="min-w-0 rounded-lg border border-line bg-panel p-3">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2 text-[13px] font-medium text-ink">
              <ServerCog size={15} className="text-brand" />
              <span>Diagnostics</span>
            </div>
            <button
              className="flex h-7 items-center gap-1.5 rounded-md px-2 text-[12px] text-muted hover:bg-hover hover:text-ink"
              type="button"
              disabled={busy}
              onClick={refreshSystem}
            >
              <RefreshCw size={13} />
              Refresh
            </button>
          </div>

          <div className="grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-2">
            <SystemMetric icon={<Database size={14} />} label="Database" value={status?.database_exists ? "Ready" : "Missing"} />
            <SystemMetric icon={<HardDrive size={14} />} label="Size" value={formatBytes(status?.database_size_bytes ?? 0)} />
            <SystemMetric icon={<FileText size={14} />} label="Logs" value={String(logs.length)} />
            <SystemMetric icon={<Brain size={14} />} label="Reflection" value={String(status?.configured["reflection_enabled"] ?? false)} />
          </div>

          <div className="mt-3 space-y-1 rounded-md border border-line bg-field p-2 text-[12px] text-sidebarInk">
            <InfoRow label="Database" value={status?.database_path} />
            <InfoRow label="Data" value={status?.data_dir} />
            <InfoRow label="Backups" value={status?.backups_dir} />
            <InfoRow label="Logs" value={status?.logs_dir} />
          </div>
        </section>

        <section className="grid min-h-0 min-w-0 grid-rows-[auto_minmax(0,1fr)] rounded-lg border border-line bg-panel">
          <div className="border-b border-line p-3">
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2 text-[13px] font-medium text-ink">
                <Database size={15} className="text-brand" />
                <span>Storage</span>
              </div>
              <button
                className="flex h-7 items-center gap-1.5 rounded-md bg-brand px-2 text-[12px] font-medium text-white hover:bg-brandStrong"
                type="button"
                disabled={busy}
                onClick={backupDatabase}
              >
                <Save size={13} />
                Backup
              </button>
            </div>
            {lastBackup ? (
              <div className="rounded-md border border-line bg-field p-2 text-[12px] text-sidebarInk">
                <div className="truncate">{lastBackup.path}</div>
                <div className="mt-1 text-muted">{formatBytes(lastBackup.size_bytes)} · {formatDateTime(lastBackup.created_at)}</div>
              </div>
            ) : null}
          </div>
          <ScrollArea.Root className="min-h-0">
            <ScrollArea.Viewport className="h-full">
              <div className="space-y-2 p-3">
                {counts.map(([key, value]) => (
                  <InfoRow key={key} label={key} value={String(value)} />
                ))}
              </div>
            </ScrollArea.Viewport>
            <ScrollArea.Scrollbar className="flex w-2 touch-none select-none bg-transparent p-0.5" orientation="vertical">
              <ScrollArea.Thumb className="relative flex-1 rounded-full bg-muted/35" />
            </ScrollArea.Scrollbar>
          </ScrollArea.Root>
        </section>
      </div>

      <div className="grid min-h-0 grid-rows-[auto_minmax(0,1fr)] gap-4">
        <section className="min-w-0 rounded-lg border border-line bg-panel p-3">
          <div className="mb-3 flex items-center gap-2 text-[13px] font-medium text-ink">
            <ServerCog size={15} className="text-brand" />
            <span>Configuration</span>
          </div>
          <div className="grid grid-cols-[repeat(auto-fit,minmax(190px,1fr))] gap-2">
            {configured.map(([key, value]) => (
              <InfoRow key={key} label={key} value={String(value)} />
            ))}
          </div>
        </section>

        <section className="grid min-h-[360px] min-w-0 grid-cols-1 overflow-hidden rounded-lg border border-line bg-panel lg:grid-cols-[220px_minmax(0,1fr)]">
          <div className="border-r border-line p-3">
            <div className="mb-3 text-[13px] font-medium text-ink">Logs</div>
            <div className="space-y-1">
              {logs.length === 0 ? (
                <div className="rounded-md px-3 py-8 text-center text-[13px] text-muted">No logs.</div>
              ) : (
                logs.map((log) => (
                  <button
                    key={log.name}
                    className={cn(
                      "w-full rounded-md px-2 py-2 text-left text-[12px] hover:bg-hover",
                      log.name === selectedLogName && "bg-active",
                    )}
                    type="button"
                    onClick={() => loadLog(log.name)}
                  >
                    <div className="truncate text-ink">{log.name}</div>
                    <div className="mt-1 text-[11px] text-muted">{formatBytes(log.size_bytes)}</div>
                  </button>
                ))
              )}
            </div>
          </div>
          <pre className="min-h-0 overflow-auto whitespace-pre-wrap p-3 font-mono text-[11px] leading-5 text-sidebarInk">
            {logTail?.content || "Select a log."}
          </pre>
        </section>
      </div>
    </div>
  );
}

function MessageBubble({
  message,
  applyStyleQuestionnaire,
  submitToolPrompt,
}: {
  message: UiMessage;
  applyStyleQuestionnaire: (profilePatch: ProfileUpdate, promptSummary: string) => void;
  submitToolPrompt: (content: string) => void;
}) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";
  if (isSystem) {
    return (
      <div className="rounded-md border border-danger/20 bg-danger/10 px-3 py-2 text-[13px] leading-5 text-ink">
        {message.content}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-[34px_minmax(0,1fr)] gap-3">
      <div
        className={cn(
          "mt-0.5 flex h-8 w-8 items-center justify-center rounded-full",
          isUser ? "bg-user text-ink" : "bg-brand text-white",
        )}
      >
        {isUser ? <Heart size={15} /> : <Bot size={16} />}
      </div>
      <div className="min-w-0">
        <div className="mb-1 flex flex-wrap items-center gap-2 text-[12px] text-sidebarInk">
          <span className="font-medium text-ink">{isUser ? "You" : "Mina"}</span>
          <span>{formatShortTime(message.created_at)}</span>
          {message.model && !isUser ? <span className="truncate text-muted">{message.model}</span> : null}
          {message.audio_url ? <Volume2 size={12} className="text-brand" /> : null}
        </div>
        {!isUser ? (
          <ToolActivity
            statuses={message.tool_statuses}
            results={message.tool_results}
            active={!message.id}
            applyStyleQuestionnaire={applyStyleQuestionnaire}
            submitToolPrompt={submitToolPrompt}
          />
        ) : null}
        <MarkdownContent content={message.content} />
        {message.audio_url ? (
          <audio className="mt-3 h-8 w-full max-w-md" controls src={audioUrl(message.audio_url) ?? undefined} />
        ) : null}
      </div>
    </div>
  );
}

function ToolActivity({
  statuses = [],
  results = [],
  active,
  applyStyleQuestionnaire,
  submitToolPrompt,
}: {
  statuses?: string[];
  results?: UiToolResult[];
  active: boolean;
  applyStyleQuestionnaire: (profilePatch: ProfileUpdate, promptSummary: string) => void;
  submitToolPrompt: (content: string) => void;
}) {
  if (statuses.length === 0 && results.length === 0) return null;
  const visibleStatuses = statuses.filter((status, index) => status && statuses.indexOf(status) === index);

  return (
    <div className="mb-3 space-y-2">
      {visibleStatuses.length ? (
        <div className="rounded-lg border border-line bg-field p-3">
          <div className="mb-2 flex items-center justify-between gap-2 text-[12px] font-semibold text-ink">
            <span>{active ? "Mina is working" : "Mina used"}</span>
            {results.length ? <span className="text-[11px] font-normal text-muted">{results.length} results</span> : null}
          </div>
          <div className="grid gap-1.5">
            {visibleStatuses.map((status, index) => {
              const isLatest = active && index === visibleStatuses.length - 1;
              return (
                <div key={`${status}-${index}`} className="flex items-center gap-2 text-[12px] text-sidebarInk">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-brandSoft text-brandStrong">
                    {isLatest ? <Loader2 size={11} className="animate-spin" /> : <Check size={11} />}
                  </span>
                  <span>{status}</span>
                </div>
              );
            })}
          </div>
        </div>
      ) : null}
      {results.map((result, index) => (
        <ToolResultCard
          key={`${result.name}-${index}`}
          result={result}
          applyStyleQuestionnaire={applyStyleQuestionnaire}
          submitToolPrompt={submitToolPrompt}
        />
      ))}
    </div>
  );
}

function ToolResultCard({
  result,
  applyStyleQuestionnaire,
  submitToolPrompt,
}: {
  result: UiToolResult;
  applyStyleQuestionnaire: (profilePatch: ProfileUpdate, promptSummary: string) => void;
  submitToolPrompt: (content: string) => void;
}) {
  if (result.name === "web_search") return <WebSearchToolCard result={result} />;
  if (result.name === "product_search" || result.name === "get_prices") return <ProductToolCard result={result} />;
  if (result.name === "preference_candidate") return <PreferenceCandidateCard result={result} />;
  if (result.name === "style_profile_questionnaire") {
    return <StyleProfileQuestionnaireCard result={result} applyStyleQuestionnaire={applyStyleQuestionnaire} />;
  }
  if (result.name === "shopping_questionnaire") {
    return <ShoppingQuestionnaireCard result={result} submitToolPrompt={submitToolPrompt} />;
  }
  if (result.name === "build_outfit") return <BuildOutfitToolCard result={result} />;
  if (result.name === "outfit_planner_guidance") {
    return (
      <div className="rounded-lg border border-brand/15 bg-brandSoft/35 p-3 text-[12px] text-sidebarInk">
        <div className="flex items-center gap-2 font-semibold text-ink">
          <Shirt size={14} className="text-brand" />
          <span>Outfit planner</span>
        </div>
      </div>
    );
  }
  if (result.name === "wardrobe_context") {
    return (
      <div className="rounded-lg border border-line bg-field p-3 text-[12px] text-sidebarInk">
        <div className="mb-1 flex items-center gap-2 font-semibold text-ink">
          <ShoppingBag size={14} className="text-brand" />
          <span>Wardrobe context</span>
        </div>
        <div>{Number(result.payload.count || 0)} matching items</div>
      </div>
    );
  }
  return null;
}

function BuildOutfitToolCard({ result }: { result: UiToolResult }) {
  const items = Array.isArray(result.payload.items) ? (result.payload.items as ChatToolOutfitItem[]) : [];
  const count = typeof result.payload.owned_count === "number" ? result.payload.owned_count : items.length;

  return (
    <div className="rounded-lg border border-line bg-field p-3">
      <div className="mb-2 flex items-center gap-2 text-[12px] font-semibold text-ink">
        <Shirt size={14} className="text-brand" />
        <span>Outfit builder</span>
        <span className="text-[11px] font-normal text-muted">{count} wardrobe items considered</span>
      </div>
      {items.length ? (
        <div className="flex flex-wrap gap-1.5">
          {items.slice(0, 8).map((item) => (
            <span
              key={`${item.id}-${item.name}`}
              className="rounded-full border border-brand/15 bg-brandSoft px-2 py-1 text-[11px] text-brandStrong"
              title={[item.category, item.colors.join(", "), item.brand].filter(Boolean).join(" · ")}
            >
              {item.name}
            </span>
          ))}
        </div>
      ) : (
        <div className="rounded-md bg-panel px-3 py-2 text-[12px] text-muted">
          No wardrobe items saved yet. Mina can still suggest missing pieces.
        </div>
      )}
    </div>
  );
}

function StyleProfileQuestionnaireCard({
  result,
  applyStyleQuestionnaire,
}: {
  result: UiToolResult;
  applyStyleQuestionnaire: (profilePatch: ProfileUpdate, promptSummary: string) => void;
}) {
  const questions = Array.isArray(result.payload.questions)
    ? (result.payload.questions as ChatToolQuestionnaireQuestion[])
    : [];
  const [answers, setAnswers] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {};
    for (const question of questions) {
      if (question.type === "single" && question.options?.[0]) initial[question.id] = question.options[0].value;
    }
    return initial;
  });
  const [step, setStep] = useState(0);
  const [applied, setApplied] = useState(false);
  const currentQuestion = questions[Math.min(step, Math.max(questions.length - 1, 0))];
  const isLastStep = step >= questions.length - 1;

  function setAnswer(questionId: string, value: string) {
    setAnswers((current) => ({ ...current, [questionId]: value }));
  }

  function skipCurrent() {
    if (!currentQuestion) return;
    setAnswers((current) => ({ ...current, [currentQuestion.id]: "" }));
    setStep((current) => Math.min(current + 1, questions.length - 1));
  }

  function nextStep() {
    setStep((current) => Math.min(current + 1, questions.length - 1));
  }

  function previousStep() {
    setStep((current) => Math.max(current - 1, 0));
  }

  function start() {
    const profilePatch: ProfileUpdate = {};
    const summaryParts: string[] = [];
    for (const question of questions) {
      const value = (answers[question.id] || "").trim();
      if (!value) continue;
      if (question.profile_field) profilePatch[question.profile_field] = value;
      if (question.type !== "text") summaryParts.push(`${question.label}: ${labelForAnswer(question, value)}`);
    }
    const extra = (answers.extra_notes || "").trim();
    const promptSummary = [
      `Tu perfil de estilo: ${summaryParts.join(" · ")}`,
      extra ? `Notas extra: ${extra}` : "",
      "Continua con recomendaciones personalizadas usando este perfil. No generes otro cuestionario; si falta algo, pregunta solo una cosa concreta.",
    ]
      .filter(Boolean)
      .join("\n");
    applyStyleQuestionnaire(profilePatch, promptSummary);
    setApplied(true);
  }

  if (!questions.length) return null;

  if (applied) {
    return (
      <div className="rounded-lg border border-brand/20 bg-brandSoft/45 p-3">
        <div className="flex items-center gap-2 text-[13px] font-semibold text-ink">
          <Check size={14} className="text-brand" />
          <span>Perfil de estilo guardado</span>
        </div>
        <div className="mt-2 space-y-1 text-[12px] leading-5 text-sidebarInk">
          {questions
            .filter((question) => (answers[question.id] || "").trim())
            .map((question) => (
              <div key={question.id}>
                <span className="font-semibold text-ink">{question.label}: </span>
                {labelForAnswer(question, answers[question.id])}
              </div>
            ))}
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-line bg-field p-3">
      <div className="border-b border-line pb-3">
        <div className="flex items-center gap-2 text-[13px] font-semibold text-ink">
          <FileText size={14} className="text-brand" />
          <span>{typeof result.payload.title === "string" ? result.payload.title : "Tu perfil de estilo"}</span>
        </div>
        <div className="mt-1 text-[12px] leading-5 text-sidebarInk">
          {typeof result.payload.intro === "string"
            ? result.payload.intro
            : "Completa esto una vez para personalizar mejor las recomendaciones."}
        </div>
      </div>

      <div className="py-3">
        <div className="mb-3 flex items-center gap-1.5">
          {questions.map((question, index) => (
            <button
              key={question.id}
              className={cn(
                "h-1.5 flex-1 rounded-full bg-line",
                index <= step && "bg-brand",
              )}
              type="button"
              title={question.label}
              aria-label={question.label}
              onClick={() => setStep(index)}
            />
          ))}
        </div>

        {currentQuestion ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div className="text-[12px] font-semibold text-ink">{currentQuestion.label}</div>
              <div className="text-[11px] text-muted">
                {step + 1} / {questions.length}
              </div>
            </div>
            {currentQuestion.type === "single" ? (
              <div className="grid gap-2 sm:grid-cols-2">
                {(currentQuestion.options || []).map((option) => {
                  const active = answers[currentQuestion.id] === option.value;
                  return (
                    <button
                      key={option.value}
                      className={cn(
                        "rounded-lg border border-line bg-panel px-3 py-2 text-left text-[12px] text-sidebarInk hover:border-brand/35 hover:bg-hover",
                        active && "border-brand bg-brandSoft text-brandStrong",
                      )}
                      type="button"
                      onClick={() => setAnswer(currentQuestion.id, option.value)}
                    >
                      <div className="font-semibold">{option.label}</div>
                      {option.description ? <div className="mt-0.5 text-[11px] opacity-75">{option.description}</div> : null}
                    </button>
                  );
                })}
              </div>
            ) : (
              <textarea
                className="min-h-24 w-full resize-none rounded-lg border border-line bg-panel px-3 py-2 text-[12px] leading-5 text-ink outline-none focus:border-brand"
                value={answers[currentQuestion.id] || ""}
                placeholder={currentQuestion.placeholder || ""}
                onChange={(event) => setAnswer(currentQuestion.id, event.target.value)}
              />
            )}
          </div>
        ) : null}
      </div>

      <div className="flex items-center justify-between gap-3 border-t border-line pt-3">
        <div className="text-[11px] text-muted">
          Se guarda como memoria estable de Mina.
        </div>
        <div className="flex items-center gap-2">
          {step > 0 ? (
            <button className="rounded-md border border-line bg-panel px-3 py-2 text-[12px] text-sidebarInk" type="button" onClick={previousStep}>
              Atrás
            </button>
          ) : null}
          {!isLastStep ? (
            <button className="rounded-md border border-line bg-panel px-3 py-2 text-[12px] text-sidebarInk" type="button" onClick={skipCurrent}>
              Saltar
            </button>
          ) : null}
          {!isLastStep ? (
            <button
              className="rounded-md bg-brand px-3 py-2 text-[12px] font-semibold text-white hover:bg-brandStrong"
              type="button"
              onClick={nextStep}
            >
              Siguiente
            </button>
          ) : (
            <button
              className="rounded-md bg-brand px-3 py-2 text-[12px] font-semibold text-white hover:bg-brandStrong"
              type="button"
              onClick={start}
            >
              Empecemos
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function labelForAnswer(question: ChatToolQuestionnaireQuestion, value: string): string {
  const option = question.options?.find((item) => item.value === value);
  return option?.label || value;
}

type QuestionnaireAnswer = string | string[];

function ShoppingQuestionnaireCard({
  result,
  submitToolPrompt,
}: {
  result: UiToolResult;
  submitToolPrompt: (content: string) => void;
}) {
  const questions = Array.isArray(result.payload.questions)
    ? (result.payload.questions as ChatToolQuestionnaireQuestion[])
    : [];
  const [answers, setAnswers] = useState<Record<string, QuestionnaireAnswer>>(() => {
    const initial: Record<string, QuestionnaireAnswer> = {};
    for (const question of questions) {
      if (question.type === "single" && question.options?.[0]) {
        initial[question.id] = question.options[0].value;
      }
      if (question.type === "multi") {
        const defaultCount = question.id === "pieces" ? 3 : question.id === "stores" ? 2 : 0;
        initial[question.id] = (question.options || []).slice(0, defaultCount).map((option) => option.value);
      }
    }
    return initial;
  });
  const [step, setStep] = useState(0);
  const [submitted, setSubmitted] = useState(false);
  const currentQuestion = questions[Math.min(step, Math.max(questions.length - 1, 0))];
  const isLastStep = step >= questions.length - 1;

  function setSingleAnswer(questionId: string, value: string) {
    setAnswers((current) => ({ ...current, [questionId]: value }));
  }

  function toggleMultiAnswer(questionId: string, value: string) {
    setAnswers((current) => {
      const existing = Array.isArray(current[questionId]) ? (current[questionId] as string[]) : [];
      const next = existing.includes(value) ? existing.filter((item) => item !== value) : [...existing, value];
      return { ...current, [questionId]: next };
    });
  }

  function answerValues(questionId: string): string[] {
    const value = answers[questionId];
    if (Array.isArray(value)) return value;
    return value ? [value] : [];
  }

  function nextStep() {
    setStep((current) => Math.min(current + 1, questions.length - 1));
  }

  function previousStep() {
    setStep((current) => Math.max(current - 1, 0));
  }

  function submitSelection() {
    const summary = questions
      .map((question) => {
        const label = labelForQuestionnaireAnswer(question, answers[question.id]);
        return label ? `- ${question.label}: ${label}` : "";
      })
      .filter(Boolean);
    const pieces = answerValues("pieces").join(" ");
    const stores = answerValues("stores").join(" ");
    const contextHint = typeof result.payload.context_hint === "string" ? result.payload.context_hint : "";
    const searchSeed = [contextHint, pieces, stores || "Chile", "precio stock disponibilidad"]
      .filter(Boolean)
      .join(" ")
      .replace(/\s+/g, " ")
      .trim();
    const prompt = [
      "Arma un plan de compra y busca en internet.",
      "",
      `Busqueda sugerida: ${searchSeed}`,
      "",
      "Preferencias seleccionadas:",
      ...summary,
      "",
      "Usa queries especificas por pieza, tienda y precio. No busques la frase operacional literal.",
    ].join("\n");
    setSubmitted(true);
    submitToolPrompt(prompt);
  }

  if (!questions.length) return null;

  if (submitted) {
    return (
      <div className="rounded-lg border border-brand/20 bg-brandSoft/45 p-3">
        <div className="flex items-center gap-2 text-[13px] font-semibold text-ink">
          <Check size={14} className="text-brand" />
          <span>Selector enviado</span>
        </div>
        <div className="mt-2 text-[12px] leading-5 text-sidebarInk">
          Mina va a armar el plan con esas preferencias y buscar productos reales.
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-line bg-field p-3">
      <div className="border-b border-line pb-3">
        <div className="flex items-center gap-2 text-[13px] font-semibold text-ink">
          <ShoppingBag size={14} className="text-brand" />
          <span>{typeof result.payload.title === "string" ? result.payload.title : "Selector de piezas"}</span>
        </div>
        <div className="mt-1 text-[12px] leading-5 text-sidebarInk">
          {typeof result.payload.intro === "string"
            ? result.payload.intro
            : "Elige prioridades para afinar la busqueda."}
        </div>
      </div>

      <div className="py-3">
        <div className="mb-3 flex items-center gap-1.5">
          {questions.map((question, index) => (
            <button
              key={question.id}
              className={cn("h-1.5 flex-1 rounded-full bg-line", index <= step && "bg-brand")}
              type="button"
              title={question.label}
              aria-label={question.label}
              onClick={() => setStep(index)}
            />
          ))}
        </div>

        {currentQuestion ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div className="text-[12px] font-semibold text-ink">{currentQuestion.label}</div>
              <div className="text-[11px] text-muted">
                {step + 1} / {questions.length}
              </div>
            </div>
            {currentQuestion.type === "single" ? (
              <div className="grid gap-2 sm:grid-cols-2">
                {(currentQuestion.options || []).map((option) => {
                  const active = answers[currentQuestion.id] === option.value;
                  return (
                    <button
                      key={option.value}
                      className={cn(
                        "rounded-lg border border-line bg-panel px-3 py-2 text-left text-[12px] text-sidebarInk hover:border-brand/35 hover:bg-hover",
                        active && "border-brand bg-brandSoft text-brandStrong",
                      )}
                      type="button"
                      onClick={() => setSingleAnswer(currentQuestion.id, option.value)}
                    >
                      <div className="font-semibold">{option.label}</div>
                      {option.description ? <div className="mt-0.5 text-[11px] opacity-75">{option.description}</div> : null}
                    </button>
                  );
                })}
              </div>
            ) : currentQuestion.type === "multi" ? (
              <div className="grid gap-2 sm:grid-cols-2">
                {(currentQuestion.options || []).map((option) => {
                  const active = answerValues(currentQuestion.id).includes(option.value);
                  return (
                    <button
                      key={option.value}
                      className={cn(
                        "flex min-h-12 items-center gap-2 rounded-lg border border-line bg-panel px-3 py-2 text-left text-[12px] text-sidebarInk hover:border-brand/35 hover:bg-hover",
                        active && "border-brand bg-brandSoft text-brandStrong",
                      )}
                      type="button"
                      onClick={() => toggleMultiAnswer(currentQuestion.id, option.value)}
                    >
                      <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded border border-line bg-field">
                        {active ? <Check size={11} /> : null}
                      </span>
                      <span className="min-w-0">
                        <span className="block font-semibold">{option.label}</span>
                        {option.description ? <span className="mt-0.5 block text-[11px] opacity-75">{option.description}</span> : null}
                      </span>
                    </button>
                  );
                })}
              </div>
            ) : (
              <textarea
                className="min-h-24 w-full resize-none rounded-lg border border-line bg-panel px-3 py-2 text-[12px] leading-5 text-ink outline-none focus:border-brand"
                value={typeof answers[currentQuestion.id] === "string" ? (answers[currentQuestion.id] as string) : ""}
                placeholder={currentQuestion.placeholder || ""}
                onChange={(event) => setSingleAnswer(currentQuestion.id, event.target.value)}
              />
            )}
          </div>
        ) : null}
      </div>

      <div className="flex items-center justify-between gap-3 border-t border-line pt-3">
        <div className="min-w-0 truncate text-[11px] text-muted">
          {typeof result.payload.context_hint === "string" ? result.payload.context_hint : "Busqueda con contexto"}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {step > 0 ? (
            <button className="rounded-md border border-line bg-panel px-3 py-2 text-[12px] text-sidebarInk" type="button" onClick={previousStep}>
              Atras
            </button>
          ) : null}
          {!isLastStep ? (
            <button
              className="rounded-md bg-brand px-3 py-2 text-[12px] font-semibold text-white hover:bg-brandStrong"
              type="button"
              onClick={nextStep}
            >
              Siguiente
            </button>
          ) : (
            <button
              className="rounded-md bg-brand px-3 py-2 text-[12px] font-semibold text-white hover:bg-brandStrong"
              type="button"
              onClick={submitSelection}
            >
              {typeof result.payload.submit_label === "string" ? result.payload.submit_label : "Buscar"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function labelForQuestionnaireAnswer(question: ChatToolQuestionnaireQuestion, value: QuestionnaireAnswer | undefined): string {
  if (Array.isArray(value)) {
    return value.map((item) => labelForAnswer(question, item)).join(", ");
  }
  if (typeof value === "string") return labelForAnswer(question, value);
  return "";
}

function ProductToolCard({ result }: { result: UiToolResult }) {
  const products = Array.isArray(result.payload.products) ? (result.payload.products as ChatToolProductResult[]) : [];
  const images = Array.isArray(result.payload.images) ? (result.payload.images as ChatToolImageResult[]) : [];
  const query = typeof result.payload.query === "string" ? result.payload.query : "product search";
  const title = result.name === "get_prices" ? "Prices & availability" : "Product results";

  return (
    <div className="rounded-lg border border-line bg-field p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-[12px] font-semibold text-ink">
        <ShoppingBag size={14} className="text-brand" />
        <span>{title}</span>
        <span className="text-[11px] font-normal text-muted">{query}</span>
      </div>

      {images.length ? (
        <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {images.slice(0, 4).map((image) => (
            <a
              key={`${image.image_url}-${image.url}`}
              className="group overflow-hidden rounded-md border border-line bg-panel"
              href={image.url}
              target="_blank"
              rel="noreferrer"
              title={image.title}
            >
              <div className="aspect-square bg-surface">
                <img
                  className="h-full w-full object-cover transition group-hover:scale-[1.02]"
                  src={image.thumbnail_url || image.image_url}
                  alt={image.title}
                  loading="lazy"
                />
              </div>
              <div className="truncate px-2 py-1 text-[11px] text-sidebarInk">{image.title}</div>
            </a>
          ))}
        </div>
      ) : null}

      {products.length ? (
        <div className="grid gap-2">
          {products.slice(0, 6).map((item, index) => (
            <a
              key={`${item.url}-${index}`}
              className="block rounded-md border border-line bg-panel px-3 py-2 hover:border-brand/25 hover:bg-hover"
              href={item.url}
              target="_blank"
              rel="noreferrer"
            >
              <div className="flex items-start gap-2">
                <span className="mt-0.5 rounded-full bg-brandSoft px-1.5 text-[11px] text-brandStrong">
                  [{item.rank || index + 1}]
                </span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[12px] font-semibold text-ink">{item.title}</div>
                  <div className="mt-1 flex flex-wrap gap-1.5 text-[11px]">
                    <span className="rounded-full bg-brandSoft px-2 py-0.5 text-brandStrong">
                      {item.price || "Price not visible"}
                    </span>
                    <span className="rounded-full bg-field px-2 py-0.5 text-sidebarInk">
                      {item.availability || "Availability not visible"}
                    </span>
                  </div>
                  {item.snippet ? (
                    <div className="mt-1 line-clamp-2 text-[11px] leading-4 text-sidebarInk">{item.snippet}</div>
                  ) : null}
                  <div className="mt-1 truncate text-[10px] text-muted">{item.url}</div>
                </div>
                <ExternalLink size={13} className="shrink-0 text-muted" />
              </div>
            </a>
          ))}
        </div>
      ) : (
        <div className="rounded-md bg-panel px-3 py-2 text-[12px] text-muted">No product results found.</div>
      )}
    </div>
  );
}

function PreferenceCandidateCard({ result }: { result: UiToolResult }) {
  const value = typeof result.payload.memory_value === "string" ? result.payload.memory_value : result.content;
  return (
    <div className="rounded-lg border border-brand/20 bg-brandSoft/45 p-3 text-[12px] text-sidebarInk">
      <div className="mb-1 flex items-center gap-2 font-semibold text-ink">
        <Brain size={14} className="text-brand" />
        <span>Preference candidate</span>
      </div>
      <div className="leading-5">{value}</div>
    </div>
  );
}

function WebSearchToolCard({ result }: { result: UiToolResult }) {
  const results = Array.isArray(result.payload.results) ? (result.payload.results as ChatToolWebResult[]) : [];
  const images = Array.isArray(result.payload.images) ? (result.payload.images as ChatToolImageResult[]) : [];
  const query = typeof result.payload.query === "string" ? result.payload.query : "web search";

  return (
    <div className="rounded-lg border border-line bg-field p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-[12px] font-semibold text-ink">
        <Globe size={14} className="text-brand" />
        <span>Internet references</span>
        <span className="text-[11px] font-normal text-muted">{query}</span>
      </div>

      {images.length ? (
        <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {images.slice(0, 4).map((image) => (
            <a
              key={`${image.image_url}-${image.url}`}
              className="group overflow-hidden rounded-md border border-line bg-panel"
              href={image.url}
              target="_blank"
              rel="noreferrer"
              title={image.title}
            >
              <div className="aspect-square bg-surface">
                <img
                  className="h-full w-full object-cover transition group-hover:scale-[1.02]"
                  src={image.thumbnail_url || image.image_url}
                  alt={image.title}
                  loading="lazy"
                />
              </div>
              <div className="truncate px-2 py-1 text-[11px] text-sidebarInk">{image.title}</div>
            </a>
          ))}
        </div>
      ) : null}

      {results.length ? (
        <div className="grid gap-2">
          {results.slice(0, 5).map((item, index) => (
            <a
              key={item.url}
              className="block rounded-md border border-line bg-panel px-3 py-2 hover:border-brand/25 hover:bg-hover"
              href={item.url}
              target="_blank"
              rel="noreferrer"
            >
              <div className="flex items-start gap-2">
                <span className="mt-0.5 rounded-full bg-brandSoft px-1.5 text-[11px] text-brandStrong">
                  [{index + 1}]
                </span>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[12px] font-semibold text-ink">{item.title}</div>
                  {item.snippet ? (
                    <div className="mt-1 line-clamp-2 text-[11px] leading-4 text-sidebarInk">{item.snippet}</div>
                  ) : null}
                  <div className="mt-1 truncate text-[10px] text-muted">{item.url}</div>
                </div>
                <ExternalLink size={13} className="shrink-0 text-muted" />
              </div>
            </a>
          ))}
        </div>
      ) : (
        <div className="rounded-md bg-panel px-3 py-2 text-[12px] text-muted">No references found.</div>
      )}
    </div>
  );
}

type MarkdownBlock =
  | { type: "paragraph"; text: string }
  | { type: "heading"; level: 1 | 2 | 3; text: string }
  | { type: "ul"; items: string[] }
  | { type: "ol"; items: string[] }
  | { type: "code"; code: string }
  | { type: "table"; headers: string[]; rows: string[][] };

function MarkdownContent({ content }: { content: string }) {
  const blocks = parseMarkdownBlocks(content);

  return (
    <div className="mina-markdown space-y-3 text-[14px] leading-7 text-ink">
      {blocks.map((block, index) => renderMarkdownBlock(block, index))}
    </div>
  );
}

function parseMarkdownBlocks(content: string): MarkdownBlock[] {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const blocks: MarkdownBlock[] = [];
  let paragraph: string[] = [];

  function flushParagraph() {
    const text = paragraph.join("\n").trim();
    if (text) blocks.push({ type: "paragraph", text });
    paragraph = [];
  }

  for (let index = 0; index < lines.length; ) {
    const line = lines[index];
    const trimmed = line.trim();

    if (!trimmed) {
      flushParagraph();
      index += 1;
      continue;
    }

    if (trimmed.startsWith("```")) {
      flushParagraph();
      index += 1;
      const codeLines: string[] = [];
      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        codeLines.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) index += 1;
      blocks.push({ type: "code", code: codeLines.join("\n") });
      continue;
    }

    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      flushParagraph();
      blocks.push({ type: "heading", level: heading[1].length as 1 | 2 | 3, text: heading[2].trim() });
      index += 1;
      continue;
    }

    if (isMarkdownTableStart(lines, index)) {
      flushParagraph();
      const headers = parseMarkdownTableRow(lines[index]);
      index += 2;
      const rows: string[][] = [];
      while (index < lines.length && isMarkdownTableRow(lines[index])) {
        const row = parseMarkdownTableRow(lines[index]);
        rows.push(normalizeTableRow(row, headers.length));
        index += 1;
      }
      blocks.push({ type: "table", headers, rows });
      continue;
    }

    const unordered = line.match(/^\s*[-*](?:\s+|$)(.*)$/);
    if (unordered) {
      flushParagraph();
      const items: string[] = [];
      while (index < lines.length) {
        const item = lines[index].match(/^\s*[-*](?:\s+|$)(.*)$/);
        if (!item) break;
        items.push(item[1].trim());
        index += 1;
      }
      blocks.push({ type: "ul", items });
      continue;
    }

    const ordered = line.match(/^\s*\d+[.)](?:\s+|$)(.*)$/);
    if (ordered) {
      flushParagraph();
      const items: string[] = [];
      while (index < lines.length) {
        const item = lines[index].match(/^\s*\d+[.)](?:\s+|$)(.*)$/);
        if (!item) break;
        items.push(item[1].trim());
        index += 1;
      }
      blocks.push({ type: "ol", items });
      continue;
    }

    paragraph.push(line);
    index += 1;
  }

  flushParagraph();
  return blocks;
}

function isMarkdownTableStart(lines: string[], index: number): boolean {
  if (index + 1 >= lines.length) return false;
  return isMarkdownTableRow(lines[index]) && isMarkdownSeparatorRow(lines[index + 1]);
}

function isMarkdownTableRow(line: string): boolean {
  const trimmed = line.trim();
  return trimmed.includes("|") && trimmed.split("|").filter((cell) => cell.trim()).length >= 2;
}

function isMarkdownSeparatorRow(line: string): boolean {
  const cells = parseMarkdownTableRow(line);
  if (cells.length < 2) return false;
  return cells.every((cell) => /^:?-{3,}:?$/.test(cell.trim()));
}

function parseMarkdownTableRow(line: string): string[] {
  const trimmed = line.trim().replace(/^\|/, "").replace(/\|$/, "");
  return trimmed.split("|").map((cell) => cell.trim());
}

function normalizeTableRow(row: string[], cellCount: number): string[] {
  if (row.length === cellCount) return row;
  if (row.length > cellCount) return row.slice(0, cellCount - 1).concat(row.slice(cellCount - 1).join(" | "));
  return [...row, ...Array.from({ length: cellCount - row.length }, () => "")];
}

function renderMarkdownBlock(block: MarkdownBlock, index: number): ReactNode {
  if (block.type === "heading") {
    return (
      <div
        key={index}
        className={cn(
          "font-semibold text-ink",
          block.level === 1 && "text-[18px] leading-7",
          block.level === 2 && "text-[16px] leading-7",
          block.level === 3 && "text-[14px] leading-6",
        )}
      >
        {renderInlineMarkdown(block.text)}
      </div>
    );
  }

  if (block.type === "ul") {
    return (
      <ul key={index} className="ml-5 list-disc space-y-1 marker:text-brand">
        {block.items.map((item, itemIndex) => (
          <li key={itemIndex}>{renderInlineMarkdown(item)}</li>
        ))}
      </ul>
    );
  }

  if (block.type === "ol") {
    return (
      <ol key={index} className="ml-5 list-decimal space-y-1 marker:text-brand">
        {block.items.map((item, itemIndex) => (
          <li key={itemIndex}>{renderInlineMarkdown(item)}</li>
        ))}
      </ol>
    );
  }

  if (block.type === "code") {
    return (
      <pre
        key={index}
        className="overflow-auto rounded-md border border-line bg-field p-3 font-mono text-[12px] leading-5 text-sidebarInk"
      >
        <code>{block.code}</code>
      </pre>
    );
  }

  if (block.type === "table") {
    return (
      <div key={index} className="overflow-x-auto rounded-lg border border-line bg-panel">
        <table className="min-w-full border-collapse text-left text-[12px] leading-5">
          <thead className="bg-brandSoft text-brandStrong">
            <tr>
              {block.headers.map((header, headerIndex) => (
                <th key={`${header}-${headerIndex}`} className="border-b border-line px-3 py-2 font-semibold">
                  {renderInlineMarkdown(header)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {block.rows.map((row, rowIndex) => (
              <tr key={rowIndex} className="border-b border-line last:border-b-0">
                {row.map((cell, cellIndex) => (
                  <td key={`${rowIndex}-${cellIndex}`} className="min-w-[120px] px-3 py-2 align-top text-ink">
                    {renderInlineMarkdown(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <p key={index} className="whitespace-pre-wrap">
      {renderInlineMarkdown(block.text)}
    </p>
  );
}

function renderInlineMarkdown(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const pattern = /(`[^`]+`|\*\*[^*]+\*\*|__[^_]+__|\*[^*\n]+\*|_[^_\n]+_)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text))) {
    if (match.index > lastIndex) nodes.push(text.slice(lastIndex, match.index));

    const token = match[0];
    const key = `${match.index}-${token}`;

    if (token.startsWith("`")) {
      nodes.push(
        <code key={key} className="rounded bg-brandSoft px-1 py-0.5 font-mono text-[12px] text-brandStrong">
          {token.slice(1, -1)}
        </code>,
      );
    } else if (token.startsWith("**") || token.startsWith("__")) {
      nodes.push(
        <strong key={key} className="font-semibold text-ink">
          {token.slice(2, -2)}
        </strong>,
      );
    } else {
      nodes.push(
        <em key={key} className="italic">
          {token.slice(1, -1)}
        </em>,
      );
    }

    lastIndex = pattern.lastIndex;
  }

  if (lastIndex < text.length) nodes.push(text.slice(lastIndex));
  return nodes;
}

function RailButton({
  active,
  title,
  children,
  onClick,
}: {
  active: boolean;
  title: string;
  children: ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      className={cn(
        "flex h-9 w-9 items-center justify-center rounded-lg text-sidebarInk hover:bg-hover hover:text-brand",
        active && "bg-brandSoft text-brand",
      )}
      type="button"
      title={title}
      aria-label={title}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function PaletteSwitch({ value, onChange }: { value: AccentTheme; onChange: (value: AccentTheme) => void }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-[12px] text-sidebarInk">
        <Palette size={14} />
        <span>Palette</span>
      </div>
      <div className="grid grid-cols-2 gap-1">
        {ACCENT_OPTIONS.map((option) => (
          <button
            key={option.id}
            className={cn(
              "flex h-7 items-center gap-1.5 rounded-md border border-line bg-field px-2 text-[11px] text-sidebarInk hover:bg-hover",
              value === option.id && "border-brand bg-brandSoft text-brand",
            )}
            type="button"
            title={option.label}
            aria-label={option.label}
            onClick={() => onChange(option.id)}
          >
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: accentPreview(option.id) }} />
            <span className="truncate">{option.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function RailPaletteDots({ value, onChange }: { value: AccentTheme; onChange: (value: AccentTheme) => void }) {
  return (
    <div className="grid grid-cols-2 gap-1 rounded-lg p-1" title="Palette">
      {ACCENT_OPTIONS.map((option) => (
        <button
          key={option.id}
          className={cn(
            "h-3.5 w-3.5 rounded-full border border-line",
            value === option.id && "ring-2 ring-brand ring-offset-1 ring-offset-sidebar",
          )}
          style={{ backgroundColor: accentPreview(option.id) }}
          type="button"
          aria-label={option.label}
          onClick={() => onChange(option.id)}
        />
      ))}
    </div>
  );
}

function sectionIcon(section: ChatSectionId): ReactNode {
  if (section === "fashion") return <Shirt size={17} />;
  if (section === "makeup") return <Brush size={17} />;
  if (section === "wardrobe") return <ShoppingBag size={17} />;
  if (section === "perfume") return <SprayCan size={17} />;
  if (section === "style") return <BookOpen size={17} />;
  return <MessageSquare size={17} />;
}

function accentPreview(theme: AccentTheme): string {
  if (theme === "pink") return "#fdebf3";
  if (theme === "purple") return "#f4edff";
  if (theme === "blue") return "#e8f3ff";
  return "#e8f6ec";
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => {
      if (typeof reader.result === "string") {
        resolve(reader.result);
      } else {
        reject(new Error("Could not read image file."));
      }
    });
    reader.addEventListener("error", () => reject(reader.error || new Error("Could not read image file.")));
    reader.readAsDataURL(file);
  });
}

function wardrobePayload(editor: WardrobeEditorState): WardrobeItemCreate {
  return {
    name: editor.name.trim(),
    category: editor.category.trim(),
    subcategory: emptyToNull(editor.subcategory),
    colors: splitList(editor.colors),
    material: emptyToNull(editor.material),
    brand: emptyToNull(editor.brand),
    size_label: emptyToNull(editor.size_label),
    fit: emptyToNull(editor.fit),
    season: emptyToNull(editor.season),
    occasions: splitList(editor.occasions),
    style_tags: splitList(editor.style_tags),
    notes: emptyToNull(editor.notes),
    favorite: editor.favorite,
    source: "desktop",
    source_id: null,
  };
}

function draftToWardrobeEditor(draft: WardrobeExtractionDraft): WardrobeEditorState {
  return {
    name: draft.name || "",
    category: draft.category || "other",
    subcategory: draft.subcategory || "",
    colors: draft.colors.join(", "),
    material: draft.material || "",
    brand: draft.brand || "",
    size_label: draft.size_label || "",
    fit: draft.fit || "",
    season: draft.season || "",
    occasions: draft.occasions.join(", "),
    style_tags: draft.style_tags.join(", "),
    notes: draft.notes || "",
    favorite: draft.favorite,
  };
}

function draftToWardrobePayload(draft: WardrobeExtractionDraft): WardrobeItemCreate {
  return {
    name: draft.name.trim(),
    category: draft.category.trim() || "other",
    subcategory: draft.subcategory,
    colors: draft.colors,
    material: draft.material,
    brand: draft.brand,
    size_label: draft.size_label,
    fit: draft.fit,
    season: draft.season,
    occasions: draft.occasions,
    style_tags: draft.style_tags,
    notes: draft.notes,
    favorite: draft.favorite,
    source: draft.source || "vision",
    source_id: draft.source_id || String(draft.source_image_id),
  };
}

function splitList(value: string): string[] {
  const seen = new Set<string>();
  return value
    .replace(/\n/g, ",")
    .split(",")
    .map((item) => item.trim())
    .filter((item) => {
      const key = item.toLowerCase();
      if (!item || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

function emptyToNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function readStoredAccentTheme(): AccentTheme {
  try {
    const stored = window.localStorage.getItem("mina.accentTheme");
    if (stored === "pink" || stored === "purple" || stored === "blue" || stored === "green") return stored;
  } catch {
    return "green";
  }
  return "green";
}

function IconButton({
  title,
  disabled,
  children,
  onClick,
}: {
  title: string;
  disabled?: boolean;
  children: ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      className="flex h-7 w-7 items-center justify-center rounded-md text-muted hover:bg-hover hover:text-ink disabled:opacity-45"
      type="button"
      title={title}
      aria-label={title}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function HeaderSelect({
  label,
  value,
  disabled,
  children,
  onChange,
}: {
  label: string;
  value: string;
  disabled?: boolean;
  children: ReactNode;
  onChange: (value: string) => void;
}) {
  return (
    <label className="min-w-0">
      <div className="mb-1 text-[11px] text-sidebarInk">{label}</div>
      <select
        className="h-8 w-full rounded-md border border-line bg-field px-2 text-[12px] text-ink outline-none"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      >
        {children}
      </select>
    </label>
  );
}

function HeaderInput({
  label,
  value,
  list,
  disabled,
  onChange,
}: {
  label: string;
  value: string;
  list?: string;
  disabled?: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <label className="min-w-0">
      <div className="mb-1 text-[11px] text-sidebarInk">{label}</div>
      <input
        className="h-8 w-full rounded-md border border-line bg-field px-2 text-[12px] text-ink outline-none"
        value={value}
        list={list}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function SystemMetric({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="rounded-md border border-line bg-field p-2">
      <div className="flex items-center gap-2 text-[11px] text-muted">
        {icon}
        {label}
      </div>
      <div className="mt-1 truncate text-[13px] font-medium text-ink">{value}</div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string | undefined }) {
  return (
    <div className="flex min-w-0 items-center justify-between gap-3 overflow-hidden rounded-md border border-line bg-field px-2 py-1.5 text-[12px] text-sidebarInk">
      <span className="shrink-0 text-muted">{label}</span>
      <span className="min-w-0 truncate text-right" title={value}>{value || "-"}</span>
    </div>
  );
}

function statusDot(kind: StatusKind) {
  if (kind === "ready") return "bg-brand";
  if (kind === "error") return "bg-danger";
  return "bg-warning";
}

function normalizeMemoryKey(value: string): string {
  return value.normalize("NFKD").replace(/\p{M}/gu, "").trim().toLowerCase()
    .replace(/[^a-z0-9_.-]+/g, ".").replace(/\.+/g, ".").replace(/^\.+|\.+$/g, "");
}

function memoryEditorError(
  editor: MemoryEditorState, items: MemoryItemResponse[], editingId: number | null,
): string | null {
  if (!editor.value.trim()) return "Write what Mina should remember.";
  if (editor.value.length > 4000) return "Memory content must be 4000 characters or fewer.";
  const key = normalizeMemoryKey(editor.key);
  if (!key && (editingId !== null || editor.key.trim())) return "Enter a valid memory key.";
  if (key.length > 160) return "The memory key must be 160 characters or fewer.";
  if (!Number.isFinite(editor.confidence) || editor.confidence < 0 || editor.confidence > 1) {
    return "Confidence must be between 0 and 1.";
  }
  if (key && items.some((item) => item.id !== editingId && item.kind === editor.kind && item.key === key)) {
    return "This key is already used in this category. Edit that memory or choose a different key.";
  }
  return null;
}

function memoryKindLabel(kind: MemoryKind): string {
  if (kind === "user_model") return "User";
  if (kind === "project_model") return "Project";
  if (kind === "episodic_event") return "Episode";
  if (kind === "relationship_signal") return "Style";
  if (kind === "personality_profile") return "Personality";
  if (kind === "self_model") return "Self";
  if (kind === "fashion_preference") return "Fashion";
  if (kind === "wardrobe_model") return "Wardrobe";
  if (kind === "style_reference") return "Reference";
  return "Media";
}

function projectSummary(project: MemoryItemResponse): string {
  try {
    const parsed = JSON.parse(project.value) as { status?: string; next_actions?: string[] };
    const actions = Array.isArray(parsed.next_actions) ? parsed.next_actions.filter(Boolean).join(", ") : "";
    return [parsed.status ? `Status: ${parsed.status}` : "", actions ? `Next: ${actions}` : ""]
      .filter(Boolean)
      .join(" · ") || project.value;
  } catch {
    return project.value;
  }
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function relativeAge(value: string): string {
  const date = new Date(value);
  const diff = Date.now() - date.getTime();
  if (!Number.isFinite(diff)) return "";
  const minutes = Math.max(0, Math.floor(diff / 60000));
  if (minutes < 1) return "now";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  return `${days}d`;
}

function formatShortTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export default App;
