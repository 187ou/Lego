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

export { API_BASE }
