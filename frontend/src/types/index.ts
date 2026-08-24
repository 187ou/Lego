/** 全局类型定义 */

export interface ToolCall {
  name: string
  args: Record<string, unknown>
  result?: Record<string, unknown>
}

export interface Message {
  id: string
  role: "user" | "assistant"
  content: string
  imageUrl?: string
  toolCalls?: ToolCall[]
  thinking?: string[]
  timestamp: string
  isStreaming?: boolean
  feedback?: 1 | -1 | null
}

export interface ConversationMeta {
  id: string
  title: string
  set_id: string
  created_at: string
  updated_at: string
}

export interface SetInfo {
  set_id: string
  name: string
  total_steps: number
  total_parts: number
  current_step: number
  thumbnail_url: string
}

export type Theme = "light" | "dark"

export interface AppSettings {
  theme: Theme
  apiBase: string
  model: string
  temperature: number
}
