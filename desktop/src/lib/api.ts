export type InputMode = "text" | "voice";
export type OutputMode = "text" | "voice" | "both";
export type TextProviderName = "ollama" | "openai" | "anthropic" | "openrouter";
export type TtsProviderName = "orpheus" | "elevenlabs" | "windows_sapi";
export type VisionProviderName = "ollama" | "openai" | "openrouter";
export type MemoryKind =
  | "user_model"
  | "project_model"
  | "episodic_event"
  | "relationship_signal"
  | "personality_profile"
  | "self_model"
  | "fashion_preference"
  | "wardrobe_model"
  | "style_reference"
  | "media_memory";
export type ReflectionCandidateStatus = "pending" | "approved" | "rejected";

export interface TextProviderStatus {
  name: TextProviderName;
  label: string;
  available: boolean;
  default_model: string;
  models: string[];
  requires_api_key: boolean;
  detail: string | null;
}

export interface VoiceOption {
  id: string;
  label: string;
  culture: string | null;
}

export interface TtsProviderStatus {
  name: TtsProviderName;
  label: string;
  available: boolean;
  default_voice: string | null;
  voices: VoiceOption[];
  requires_api_key: boolean;
  detail: string | null;
}

export interface VisionProviderStatus {
  name: VisionProviderName;
  label: string;
  available: boolean;
  default_model: string;
  models: string[];
  requires_api_key: boolean;
  detail: string | null;
}

export interface HealthResponse {
  app: string;
  database_path: string;
  text_provider: TextProviderName;
  text_providers: TextProviderStatus[];
  ollama_available: boolean;
  ollama_models: string[];
  tts_provider: TtsProviderName;
  tts_providers: TtsProviderStatus[];
  tts_available: boolean;
  tts_voices: string[];
  vision_provider: VisionProviderName;
  vision_providers: VisionProviderStatus[];
}

export interface SessionResponse {
  id: string;
  title: string | null;
  started_at: string;
  updated_at: string;
  ended_at: string | null;
  summary: string | null;
  message_count: number;
}

export interface MessageResponse {
  id: number;
  session_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
  tokens: number | null;
  model: string | null;
  audio_url: string | null;
  audio_provider: string | null;
  audio_voice: string | null;
}

export interface ChatRequest {
  content: string;
  session_id: string | null;
  input_mode: InputMode;
  output_mode: OutputMode;
  provider: TextProviderName | null;
  model: string | null;
}

export interface TtsRequest {
  text: string;
  provider: TtsProviderName | null;
  voice: string | null;
  message_id: number | null;
}

export interface TtsResponse {
  audio_id: string;
  audio_url: string;
  provider: TtsProviderName;
  voice: string | null;
  message_id: number | null;
}

export interface MemoryItemResponse {
  id: number;
  kind: MemoryKind;
  key: string;
  value: string;
  confidence: number;
  source: string | null;
  source_id: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface ProfileResponse {
  display_name: string;
  gender_identity: string;
  age_range: string;
  city: string;
  height: string;
  body_notes: string;
  size_tops: string;
  size_bottoms: string;
  size_shoes: string;
  fit_preferences: string;
  favorite_colors: string;
  avoided_colors: string;
  style_keywords: string;
  primary_occasion: string;
  style_focus: string;
  comfort_notes: string;
  budget_notes: string;
  privacy_notes: string;
  updated_at: string | null;
}

export type ProfileUpdate = Partial<Omit<ProfileResponse, "updated_at">>;

export interface WardrobeItemResponse {
  id: number;
  name: string;
  category: string;
  subcategory: string | null;
  colors: string[];
  material: string | null;
  brand: string | null;
  size_label: string | null;
  fit: string | null;
  season: string | null;
  occasions: string[];
  style_tags: string[];
  notes: string | null;
  favorite: boolean;
  source: string | null;
  source_id: string | null;
  image_count: number;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface WardrobeItemCreate {
  name: string;
  category: string;
  subcategory: string | null;
  colors: string[];
  material: string | null;
  brand: string | null;
  size_label: string | null;
  fit: string | null;
  season: string | null;
  occasions: string[];
  style_tags: string[];
  notes: string | null;
  favorite: boolean;
  source: string | null;
  source_id: string | null;
}

export type WardrobeItemUpdate = Partial<WardrobeItemCreate>;

export interface WardrobeImageResponse {
  id: number;
  item_id: number | null;
  image_url: string;
  thumbnail_url: string | null;
  original_name: string | null;
  mime_type: string | null;
  width: number | null;
  height: number | null;
  analysis: string | null;
  created_at: string;
  deleted_at: string | null;
}

export interface WardrobeImageUpload {
  data_url: string;
  original_name: string | null;
  item_id: number | null;
}

export interface WardrobeImageUpdate {
  item_id?: number | null;
  analysis?: string | null;
}

export interface VisionAnalyzeRequest {
  image_id: number;
  prompt: string | null;
  provider: VisionProviderName | null;
  model: string | null;
  save_memory: boolean;
}

export interface VisionAnalyzeResponse {
  image: WardrobeImageResponse;
  provider: VisionProviderName;
  model: string;
  analysis: string;
  memory_item: MemoryItemResponse | null;
}

export interface VisionCompareRequest {
  image_ids: number[];
  prompt: string | null;
  provider: VisionProviderName | null;
  model: string | null;
  save_memory: boolean;
}

export interface VisionCompareResponse {
  images: WardrobeImageResponse[];
  provider: VisionProviderName;
  model: string;
  analysis: string;
  memory_item: MemoryItemResponse | null;
}

export type WebSearchProvider = "duckduckgo" | "brave";

export interface WebSearchRequest {
  query: string;
  provider: WebSearchProvider | null;
  limit: number | null;
}

export interface WebSearchResultResponse {
  title: string;
  url: string;
  snippet: string | null;
  source: string;
}

export interface WebSearchResponse {
  query: string;
  provider: WebSearchProvider;
  results: WebSearchResultResponse[];
}

export interface StyleResearchRequest {
  query: string;
  search_provider: WebSearchProvider | null;
  search_limit: number | null;
  provider: TextProviderName | null;
  model: string | null;
}

export interface StyleResearchResponse {
  query: string;
  brief: string;
  provider: TextProviderName;
  model: string;
  search: WebSearchResponse;
}

export interface OutfitPlanRequest {
  prompt: string;
  web_query: string | null;
  search_provider: WebSearchProvider | null;
  search_limit: number | null;
  provider: TextProviderName | null;
  model: string | null;
}

export interface OutfitPlanResponse {
  prompt: string;
  plan: string;
  provider: TextProviderName;
  model: string;
  search: WebSearchResponse | null;
}

export interface WardrobeExtractionDraft {
  source_image_id: number;
  name: string;
  category: string;
  subcategory: string | null;
  colors: string[];
  material: string | null;
  brand: string | null;
  size_label: string | null;
  fit: string | null;
  season: string | null;
  occasions: string[];
  style_tags: string[];
  notes: string | null;
  favorite: boolean;
  confidence: number;
  source: string | null;
  source_id: string | null;
  raw_analysis: string;
}

export interface WardrobeImageExtractRequest {
  prompt: string | null;
  provider: VisionProviderName | null;
  model: string | null;
}

export interface WardrobeImageExtractResponse {
  image: WardrobeImageResponse;
  provider: VisionProviderName;
  model: string;
  draft: WardrobeExtractionDraft;
  raw_analysis: string;
}

export interface MemoryItemCreate {
  kind: MemoryKind;
  key: string;
  value: string;
  confidence: number;
  source: string | null;
  source_id: string | null;
}

export interface MemoryItemUpdate {
  kind?: MemoryKind;
  key?: string;
  value?: string;
  confidence?: number;
  source?: string | null;
  source_id?: string | null;
}

export interface ContextMessage {
  role: string;
  content: string;
}

export interface ContextPreviewResponse {
  intent: string;
  intent_reasons: string[];
  system_context: string;
  memory_items: MemoryItemResponse[];
  semantic_items: MemoryItemResponse[];
  messages: ContextMessage[];
}

export interface ProjectCreate {
  name: string;
  status: string;
  next_actions: string[];
}

export interface SemanticStatusResponse {
  enabled: boolean;
  available: boolean;
  collection: string;
  qdrant_url: string;
  embedding_model: string;
  detail: string | null;
}

export interface SemanticIndexResponse {
  indexed: number;
  skipped: number;
  collection: string;
}

export interface SemanticSearchResultResponse {
  score: number;
  memory_item: MemoryItemResponse | null;
  payload: Record<string, unknown>;
}

export interface ReflectionRunRequest {
  session_id: string;
  provider: TextProviderName | null;
  model: string | null;
  limit: number | null;
}

export interface ReflectionCandidateUpdate {
  kind?: MemoryKind;
  key?: string;
  value?: string;
  confidence?: number;
  rationale?: string | null;
  evidence?: string | null;
}

export interface ReflectionCandidateResponse {
  id: number;
  session_id: string | null;
  kind: MemoryKind;
  key: string;
  value: string;
  confidence: number;
  rationale: string | null;
  evidence: string | null;
  source: string;
  source_message_ids: number[];
  status: ReflectionCandidateStatus;
  memory_item_id: number | null;
  created_at: string;
  updated_at: string;
  reviewed_at: string | null;
}

export interface ReflectionRunResponse {
  candidates: ReflectionCandidateResponse[];
  skipped: number;
  provider: TextProviderName;
  model: string;
  source: string;
}

export interface ReflectionReviewResponse {
  candidate: ReflectionCandidateResponse;
  memory_item: MemoryItemResponse | null;
}

export interface SystemStatusResponse {
  app: string;
  project_root: string;
  data_dir: string;
  database_path: string;
  database_exists: boolean;
  database_size_bytes: number;
  audio_dir: string;
  media_dir: string;
  backups_dir: string;
  logs_dir: string;
  counts: Record<string, number>;
  configured: Record<string, unknown>;
}

export interface SystemBackupResponse {
  path: string;
  size_bytes: number;
  created_at: string;
}

export interface SystemLogFileResponse {
  name: string;
  path: string;
  size_bytes: number;
  modified_at: string | null;
}

export interface SystemLogTailResponse {
  name: string;
  content: string;
  lines: number;
  truncated: boolean;
}

export interface TurnStartedEvent {
  type: "turn_started";
  session_id: string;
  user_message_id: number;
  input_mode: InputMode;
  output_mode: OutputMode;
  provider: TextProviderName;
  model: string;
}

export interface AssistantChunkEvent {
  type: "assistant_chunk";
  session_id: string;
  delta: string;
  provider: TextProviderName;
  model: string;
}

export interface ToolStatusEvent {
  type: "tool_status";
  session_id: string;
  status: string;
}

export interface ChatToolWebResult {
  title: string;
  url: string;
  snippet: string | null;
  source: string;
}

export interface ChatToolImageResult {
  title: string;
  url: string;
  image_url: string;
  thumbnail_url: string | null;
  source: string;
}

export interface ChatToolProductResult {
  rank: number;
  title: string;
  url: string;
  snippet: string | null;
  source: string;
  price: string | null;
  availability: string | null;
}

export interface ChatToolOutfitItem {
  id: number;
  name: string;
  category: string;
  colors: string[];
  brand: string | null;
  season: string | null;
  occasions: string[];
  style_tags: string[];
  favorite: boolean;
}

export interface ChatToolQuestionnaireOption {
  label: string;
  value: string;
  description?: string;
}

export interface ChatToolQuestionnaireQuestion {
  id: string;
  profile_field?: keyof ProfileUpdate;
  label: string;
  type: "single" | "multi" | "text";
  options?: ChatToolQuestionnaireOption[];
  placeholder?: string;
}

export interface ChatToolResultPayload {
  query?: string;
  provider?: string;
  count?: number;
  results?: ChatToolWebResult[];
  images?: ChatToolImageResult[];
  products?: ChatToolProductResult[];
  owned_count?: number;
  items?: ChatToolOutfitItem[];
  title?: string;
  intro?: string;
  ui_schema?: string;
  context_hint?: string;
  submit_label?: string;
  missing_fields?: string[];
  questions?: ChatToolQuestionnaireQuestion[];
  memory_kind?: string;
  memory_key?: string;
  memory_value?: string;
  [key: string]: unknown;
}

export interface ToolResultEvent {
  type: "tool_result";
  session_id: string;
  name: string;
  status: string;
  content: string;
  payload: ChatToolResultPayload;
}

export interface AssistantMessageEvent {
  type: "assistant_message";
  final: true;
  data: {
    session_id: string;
    user_message_id: number;
    assistant_message_id: number;
    content: string;
    input_mode: InputMode;
    output_mode: OutputMode;
    provider: TextProviderName;
    model: string;
    tokens_used: number | null;
  };
}

export interface StatusEvent {
  type: "status";
  status: string;
}

export interface ErrorEvent {
  type: "error";
  detail: string;
}

export type ChatStreamEvent =
  | TurnStartedEvent
  | ToolStatusEvent
  | ToolResultEvent
  | AssistantChunkEvent
  | AssistantMessageEvent
  | StatusEvent
  | ErrorEvent;

export function getBackendUrl(): string {
  return (window.minaDesktop?.backendUrl || import.meta.env.VITE_MINA_BACKEND_URL || "http://127.0.0.1:8000")
    .replace(/\/$/, "");
}

export function getWebSocketUrl(): string {
  const backend = getBackendUrl();
  return backend.replace(/^http:/, "ws:").replace(/^https:/, "wss:") + "/ws/chat";
}

export function audioUrl(path: string | null): string | null {
  if (!path) return null;
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return `${getBackendUrl()}${path}`;
}

export function mediaUrl(path: string | null): string | null {
  if (!path) return null;
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return `${getBackendUrl()}${path}`;
}

export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getBackendUrl()}${path}`, init);
  if (!response.ok) {
    throw new Error(await responseDetail(response));
  }
  return response.json() as Promise<T>;
}

export function getHealth(): Promise<HealthResponse> {
  return fetchJson<HealthResponse>("/api/health");
}

export function getSystemStatus(): Promise<SystemStatusResponse> {
  return fetchJson<SystemStatusResponse>("/api/system/status");
}

export function createSystemBackup(): Promise<SystemBackupResponse> {
  return fetchJson<SystemBackupResponse>("/api/system/backup", { method: "POST" });
}

export function getSystemLogs(): Promise<SystemLogFileResponse[]> {
  return fetchJson<SystemLogFileResponse[]>("/api/system/logs");
}

export function getSystemLogTail(name: string, lines = 200): Promise<SystemLogTailResponse> {
  const params = new URLSearchParams({ name, lines: String(lines) });
  return fetchJson<SystemLogTailResponse>(`/api/system/logs/tail?${params.toString()}`);
}

export function getSessions(): Promise<SessionResponse[]> {
  return fetchJson<SessionResponse[]>("/api/sessions?limit=50");
}

export function getMessages(sessionId: string): Promise<MessageResponse[]> {
  return fetchJson<MessageResponse[]>(`/api/sessions/${sessionId}/messages`);
}

export async function deleteSession(sessionId: string): Promise<void> {
  await fetchJson<{ deleted: boolean }>(`/api/sessions/${sessionId}`, { method: "DELETE" });
}

export function synthesizeSpeech(request: TtsRequest): Promise<TtsResponse> {
  return fetchJson<TtsResponse>("/api/tts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export function getMemoryItems(kind?: MemoryKind): Promise<MemoryItemResponse[]> {
  const params = kind ? `?kind=${encodeURIComponent(kind)}` : "";
  return fetchJson<MemoryItemResponse[]>(`/api/memory/items${params}`);
}

export function createMemoryItem(request: MemoryItemCreate): Promise<MemoryItemResponse> {
  return fetchJson<MemoryItemResponse>("/api/memory/items", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export function updateMemoryItem(itemId: number, request: MemoryItemUpdate): Promise<MemoryItemResponse> {
  return fetchJson<MemoryItemResponse>(`/api/memory/items/${itemId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export async function deleteMemoryItem(itemId: number): Promise<void> {
  await fetchJson<{ deleted: boolean }>(`/api/memory/items/${itemId}`, { method: "DELETE" });
}

export function getProfile(): Promise<ProfileResponse> {
  return fetchJson<ProfileResponse>("/api/profile");
}

export function updateProfile(request: ProfileUpdate): Promise<ProfileResponse> {
  return fetchJson<ProfileResponse>("/api/profile", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export function getWardrobeItems(query?: string): Promise<WardrobeItemResponse[]> {
  const params = new URLSearchParams({ limit: "200" });
  if (query?.trim()) params.set("q", query.trim());
  return fetchJson<WardrobeItemResponse[]>(`/api/wardrobe/items?${params.toString()}`);
}

export function createWardrobeItem(request: WardrobeItemCreate): Promise<WardrobeItemResponse> {
  return fetchJson<WardrobeItemResponse>("/api/wardrobe/items", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export function updateWardrobeItem(itemId: number, request: WardrobeItemUpdate): Promise<WardrobeItemResponse> {
  return fetchJson<WardrobeItemResponse>(`/api/wardrobe/items/${itemId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export async function deleteWardrobeItem(itemId: number): Promise<void> {
  await fetchJson<{ deleted: boolean }>(`/api/wardrobe/items/${itemId}`, { method: "DELETE" });
}

export function getWardrobeImages(itemId?: number | null): Promise<WardrobeImageResponse[]> {
  const params = new URLSearchParams({ limit: "200" });
  if (itemId) params.set("item_id", String(itemId));
  return fetchJson<WardrobeImageResponse[]>(`/api/wardrobe/images?${params.toString()}`);
}

export function uploadWardrobeImage(request: WardrobeImageUpload): Promise<WardrobeImageResponse> {
  return fetchJson<WardrobeImageResponse>("/api/wardrobe/images", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export function updateWardrobeImage(imageId: number, request: WardrobeImageUpdate): Promise<WardrobeImageResponse> {
  return fetchJson<WardrobeImageResponse>(`/api/wardrobe/images/${imageId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export async function deleteWardrobeImage(imageId: number): Promise<void> {
  await fetchJson<{ deleted: boolean }>(`/api/wardrobe/images/${imageId}`, { method: "DELETE" });
}

export function analyzeWardrobeImage(request: VisionAnalyzeRequest): Promise<VisionAnalyzeResponse> {
  return fetchJson<VisionAnalyzeResponse>("/api/vision/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export function compareWardrobeImages(request: VisionCompareRequest): Promise<VisionCompareResponse> {
  return fetchJson<VisionCompareResponse>("/api/vision/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export function extractWardrobeImage(
  imageId: number,
  request: WardrobeImageExtractRequest,
): Promise<WardrobeImageExtractResponse> {
  return fetchJson<WardrobeImageExtractResponse>(`/api/wardrobe/images/${imageId}/extract`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export function searchWeb(request: WebSearchRequest): Promise<WebSearchResponse> {
  return fetchJson<WebSearchResponse>("/api/web/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export function createStyleResearch(request: StyleResearchRequest): Promise<StyleResearchResponse> {
  return fetchJson<StyleResearchResponse>("/api/style/research", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export function createOutfitPlan(request: OutfitPlanRequest): Promise<OutfitPlanResponse> {
  return fetchJson<OutfitPlanResponse>("/api/style/outfit-plan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export function getProjects(): Promise<MemoryItemResponse[]> {
  return fetchJson<MemoryItemResponse[]>("/api/projects");
}

export function createProject(request: ProjectCreate): Promise<MemoryItemResponse> {
  return fetchJson<MemoryItemResponse>("/api/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export function getContextPreview(sessionId: string | null, content: string): Promise<ContextPreviewResponse> {
  const params = new URLSearchParams({ content });
  if (sessionId) params.set("session_id", sessionId);
  return fetchJson<ContextPreviewResponse>(`/api/context?${params.toString()}`);
}

export function getSemanticStatus(): Promise<SemanticStatusResponse> {
  return fetchJson<SemanticStatusResponse>("/api/semantic/status");
}

export function indexSemanticMemory(kind?: MemoryKind | null): Promise<SemanticIndexResponse> {
  const params = new URLSearchParams();
  if (kind) params.set("kind", kind);
  const suffix = params.size ? `?${params.toString()}` : "";
  return fetchJson<SemanticIndexResponse>(`/api/semantic/index${suffix}`, { method: "POST" });
}

export function searchSemanticMemory(query: string, limit = 8): Promise<SemanticSearchResultResponse[]> {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  return fetchJson<SemanticSearchResultResponse[]>(`/api/semantic/search?${params.toString()}`);
}

export function getReflectionCandidates(
  status: ReflectionCandidateStatus | null = "pending",
): Promise<ReflectionCandidateResponse[]> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  const suffix = params.size ? `?${params.toString()}` : "";
  return fetchJson<ReflectionCandidateResponse[]>(`/api/reflections/candidates${suffix}`);
}

export function runReflection(request: ReflectionRunRequest): Promise<ReflectionRunResponse> {
  return fetchJson<ReflectionRunResponse>("/api/reflections/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export function updateReflectionCandidate(
  candidateId: number,
  request: ReflectionCandidateUpdate,
): Promise<ReflectionCandidateResponse> {
  return fetchJson<ReflectionCandidateResponse>(`/api/reflections/candidates/${candidateId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export function approveReflectionCandidate(candidateId: number): Promise<ReflectionReviewResponse> {
  return fetchJson<ReflectionReviewResponse>(`/api/reflections/candidates/${candidateId}/approve`, {
    method: "POST",
  });
}

export function rejectReflectionCandidate(candidateId: number): Promise<ReflectionCandidateResponse> {
  return fetchJson<ReflectionCandidateResponse>(`/api/reflections/candidates/${candidateId}/reject`, {
    method: "POST",
  });
}

async function responseDetail(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    if (typeof payload.detail === "string") return payload.detail;
    if (Array.isArray(payload.detail)) {
      return payload.detail.map((issue: { loc?: Array<string | number>; msg?: string }) => {
        const field = issue.loc?.filter((part) => part !== "body").join(".");
        return `${field ? `${field}: ` : ""}${issue.msg || "Invalid value"}`;
      }).join("; ");
    }
    return JSON.stringify(payload.detail ?? payload);
  } catch {
    return response.statusText || `HTTP ${response.status}`;
  }
}
