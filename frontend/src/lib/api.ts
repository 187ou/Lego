/** API 客户端封装 */

const API_BASE = "http://127.0.0.1:8000"

export interface ConversationMeta {
  id: string
  title: string
  set_id: string
  created_at: string
  updated_at: string
}

export interface StoredMessage {
  id: string
  role: string
  content: string
  image_url?: string
  tool_calls?: { name: string; args: Record<string, unknown> }[]
  thinking?: string[]
  timestamp: string
  feedback?: number | null
}

export interface SetInfo {
  set_id: string
  name: string
  total_steps: number
  total_parts: number
  current_step: number
  thumbnail_url: string
}

// ===== 对话管理 =====

export async function listConversations(): Promise<ConversationMeta[]> {
  const res = await fetch(`${API_BASE}/api/conversations`)
  const data = await res.json()
  return data.conversations || []
}

export async function createConversation(setId?: string, title?: string): Promise<ConversationMeta> {
  const res = await fetch(`${API_BASE}/api/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ set_id: setId || "", title: title || "" }),
  })
  const data = await res.json()
  return data.conversation
}

export async function getConversation(convId: string): Promise<{ meta: ConversationMeta; messages: StoredMessage[] }> {
  const res = await fetch(`${API_BASE}/api/conversations/${convId}`)
  if (!res.ok) throw new Error("对话不存在")
  return res.json()
}

export async function deleteConversation(convId: string): Promise<void> {
  await fetch(`${API_BASE}/api/conversations/${convId}`, { method: "DELETE" })
}

export async function updateConversation(convId: string, updates: { title?: string; set_id?: string }): Promise<ConversationMeta> {
  const res = await fetch(`${API_BASE}/api/conversations/${convId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  })
  const data = await res.json()
  return data.conversation
}

export async function setMessageFeedback(convId: string, messageId: string, feedback: number | null): Promise<void> {
  await fetch(`${API_BASE}/api/conversations/${convId}/messages/${messageId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ feedback }),
  })
}

// ===== 套装管理 =====

export async function listSets(): Promise<SetInfo[]> {
  const res = await fetch(`${API_BASE}/api/sets`)
  const data = await res.json()
  return data.sets || []
}

export async function getSet(setId: string): Promise<SetInfo> {
  const res = await fetch(`${API_BASE}/api/sets/${setId}`)
  const data = await res.json()
  return data.set
}

export async function updateProgress(setId: string, currentStep: number): Promise<SetInfo> {
  const res = await fetch(`${API_BASE}/api/sets/${setId}/progress`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ current_step: currentStep }),
  })
  const data = await res.json()
  return data.set
}

// ===== 健康检查 =====

export async function checkHealth(): Promise<{ status: string; redis: boolean }> {
  const res = await fetch(`${API_BASE}/api/health`)
  return res.json()
}

// ===== 记忆管理 =====

export interface ConversationSummary {
  conversation_id: string
  set_id: string
  summary: string
  key_events: string[]
  total_messages: number
  total_steps_covered: number[]
  parts_discussed: string[]
  created_at: string
}

export interface UserProfile {
  user_id: string
  skill_level: string
  preferred_sets: string[]
  common_parts: string[]
  total_conversations: number
  total_messages: number
  avg_frustration_score: number
  language: string
  response_style: string
  first_seen: string
  last_seen: string
}

export async function getMemoryStatus(): Promise<{ redis_available: boolean; cache_info: dict }> {
  const res = await fetch(`${API_BASE}/api/memory/status`)
  return res.json()
}

export async function getConversationSummary(convId: string): Promise<ConversationSummary> {
  const res = await fetch(`${API_BASE}/api/memory/conversations/${convId}/summary`)
  if (!res.ok) throw new Error("摘要不存在")
  const data = await res.json()
  return data.summary
}

export async function getConversationMessages(
  convId: string,
  limit?: number,
  offset?: number,
): Promise<{ messages: StoredMessage[]; total: number }> {
  const params = new URLSearchParams()
  if (limit) params.set("limit", String(limit))
  if (offset) params.set("offset", String(offset))
  const res = await fetch(`${API_BASE}/api/memory/conversations/${convId}/messages?${params}`)
  return res.json()
}

export async function getSetSummaries(setId: string, limit = 5): Promise<ConversationSummary[]> {
  const res = await fetch(`${API_BASE}/api/memory/sets/${setId}/summaries?limit=${limit}`)
  const data = await res.json()
  return data.summaries || []
}

export async function getUserProfile(userId = "default"): Promise<UserProfile> {
  const res = await fetch(`${API_BASE}/api/memory/user/profile?user_id=${userId}`)
  const data = await res.json()
  return data.profile
}

export async function generateSummary(convId: string): Promise<ConversationSummary> {
  const res = await fetch(`${API_BASE}/api/memory/conversations/${convId}/summary`, {
    method: "POST",
  })
  if (!res.ok) throw new Error("生成摘要失败")
  const data = await res.json()
  return data.summary
}

export async function clearMemoryCache(): Promise<void> {
  await fetch(`${API_BASE}/api/memory/cache`, { method: "DELETE" })
}

// ===== 文档上传/向量库管理 =====

export interface DocumentUploadResult {
  success: boolean
  filename: string
  set_id: string
  documents_added: number
  message: string
}

export interface DocumentStats {
  total_documents: number
  cached_documents: number
  collection_name: string
  sets: string[]
}

export interface SearchResult {
  content: string
  metadata: Record<string, unknown>
  score: number
  match_type: string
}

export async function uploadDocument(file: File, setId: string): Promise<DocumentUploadResult> {
  const formData = new FormData()
  formData.append("file", file)
  formData.append("set_id", setId)

  const res = await fetch(`${API_BASE}/api/documents/upload`, {
    method: "POST",
    body: formData,
  })
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || "上传失败")
  }
  return res.json()
}

export async function importMockData(): Promise<{ success: boolean; documents_added: number; message: string }> {
  const res = await fetch(`${API_BASE}/api/documents/import-mock`, { method: "POST" })
  return res.json()
}

export async function getDocumentStats(): Promise<DocumentStats> {
  const res = await fetch(`${API_BASE}/api/documents/stats`)
  return res.json()
}

export async function deleteSetDocuments(setId: string): Promise<{ success: boolean; deleted: number }> {
  const res = await fetch(`${API_BASE}/api/documents/set/${setId}`, { method: "DELETE" })
  return res.json()
}

export async function searchDocuments(
  query: string,
  setId?: string,
  topK?: number,
  docType?: string,
): Promise<{ results: SearchResult[]; query: string }> {
  const params = new URLSearchParams()
  params.set("query", query)
  if (setId) params.set("set_id", setId)
  if (topK) params.set("top_k", String(topK))
  if (docType) params.set("doc_type", docType)

  const res = await fetch(`${API_BASE}/api/documents/search?${params}`)
  return res.json()
}

export { API_BASE }
