/** 聊天状态 Store - 核心状态管理 */

import { create } from "zustand"
import type { Message, ConversationMeta, SetInfo } from "../types"
import {
  listConversations,
  createConversation,
  getConversation,
  deleteConversation,
  updateConversation,
  setMessageFeedback,
  listSets,
  getSet,
  updateProgress,
} from "../lib/api"
import { useSettingsStore } from "./settingsStore"

interface ChatState {
  // 对话列表
  conversations: ConversationMeta[]
  currentConversationId: string | null

  // 当前消息
  messages: Message[]
  isStreaming: boolean
  streamingMessageId: string | null

  // 思考过程
  currentThinking: string[]

  // 套装
  sets: SetInfo[]
  currentSet: SetInfo | null

  // HITL 确认
  pendingConfirmation: { messageId: string; toolName: string; args: Record<string, unknown> } | null

  // 挫折感知
  frustrationScore: number
  encouragementMessages: string[]

  // Actions
  loadConversations: () => Promise<void>
  createNewConversation: (setId?: string) => Promise<void>
  switchConversation: (id: string) => Promise<void>
  deleteConversation: (id: string) => Promise<void>
  sendMessage: (content: string, image?: File) => Promise<void>
  regenerateMessage: (messageId: string) => Promise<void>
  setMessageFeedback: (messageId: string, feedback: 1 | -1 | null) => void
  loadSets: () => Promise<void>
  setCurrentSet: (setId: string) => Promise<void>
  updateSetProgress: (step: number) => Promise<void>
  confirmAction: (messageId: string) => void
  cancelAction: (messageId: string) => void
}

export const useChatStore = create<ChatState>((set, get) => ({
  conversations: [],
  currentConversationId: null,
  messages: [],
  isStreaming: false,
  streamingMessageId: null,
  currentThinking: [],
  sets: [],
  currentSet: null,
  pendingConfirmation: null,
  frustrationScore: 0,
  encouragementMessages: [],

  loadConversations: async () => {
    try {
      const convs = await listConversations()
      set({ conversations: convs })
    } catch {
      set({ conversations: [] })
    }
  },

  createNewConversation: async (setId?: string) => {
    try {
      const meta = await createConversation(setId)
      set((state) => ({
        conversations: [meta, ...state.conversations],
        currentConversationId: meta.id,
        messages: [],
        currentSet: state.currentSet,
      }))
    } catch {
      // Redis 不可用时创建本地对话
      const id = Date.now().toString()
      set((state) => ({
        conversations: [
          {
            id,
            title: "新对话",
            set_id: setId || "",
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
          ...state.conversations,
        ],
        currentConversationId: id,
        messages: [],
      }))
    }
  },

  switchConversation: async (id: string) => {
    try {
      const data = await getConversation(id)
      set({
        currentConversationId: id,
        messages: data.messages.map((m) => ({
          id: m.id,
          role: m.role as "user" | "assistant",
          content: m.content,
          imageUrl: m.image_url,
          toolCalls: m.tool_calls,
          thinking: m.thinking,
          timestamp: m.timestamp,
          feedback: m.feedback,
        })),
      })
    } catch {
      set({ currentConversationId: id, messages: [] })
    }
  },

  deleteConversation: async (id: string) => {
    try {
      await deleteConversation(id)
    } catch {
      // ignore
    }
    set((state) => {
      const remaining = state.conversations.filter((c) => c.id !== id)
      if (state.currentConversationId === id) {
        return {
          conversations: remaining,
          currentConversationId: remaining[0]?.id || null,
          messages: [],
        }
      }
      return { conversations: remaining }
    })
    // 如果删除的是当前对话，切换到下一个
    const { currentConversationId, conversations } = get()
    if (!currentConversationId && conversations.length > 0) {
      get().switchConversation(conversations[0].id)
    }
  },

  sendMessage: async (content: string, image?: File) => {
    const { currentConversationId, currentSet } = get()
    if (!currentConversationId) return

    const apiBase = useSettingsStore.getState().apiBase
    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content,
      imageUrl: image ? URL.createObjectURL(image) : undefined,
      timestamp: new Date().toISOString(),
    }

    const streamingId = (Date.now() + 1).toString()
    const streamingMessage: Message = {
      id: streamingId,
      role: "assistant",
      content: "",
      thinking: [],
      timestamp: new Date().toISOString(),
      isStreaming: true,
    }

    set((state) => ({
      messages: [...state.messages, userMessage, streamingMessage],
      isStreaming: true,
      streamingMessageId: streamingId,
      currentThinking: ["🤔 正在分析你的问题..."],
    }))

    try {
      if (image) {
        // 图片上传（非流式）
        const formData = new FormData()
        formData.append("image", image)
        formData.append("message", content)
        formData.append("set_id", currentSet?.set_id || "")
        formData.append("conversation_id", currentConversationId)

        const response = await fetch(`${apiBase}/api/chat/image`, {
          method: "POST",
          body: formData,
        })
        const data = await response.json()

        set((state) => ({
          messages: state.messages.map((msg) =>
            msg.id === streamingId
              ? {
                  ...msg,
                  content: data.response,
                  toolCalls: data.tool_calls,
                  isStreaming: false,
                }
              : msg
          ),
          isStreaming: false,
          streamingMessageId: null,
          currentThinking: [],
        }))
      } else {
        // 流式聊天
        const response = await fetch(`${apiBase}/api/chat/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: content,
            set_id: currentSet?.set_id || "",
            conversation_id: currentConversationId,
          }),
        })

        if (!response.body) throw new Error("No response body")

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ""
        let thinkingSteps: string[] = []
        let responseText = ""
        let toolCalls: { name: string; args: Record<string, unknown> }[] = []

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split("\n")
          buffer = lines.pop() || ""

          for (const line of lines) {
            if (line.startsWith("event: ")) {
              const event = line.slice(7)
              const idx = lines.indexOf(line)
              const dataLine = lines[idx + 1]
              if (dataLine?.startsWith("data: ")) {
                const data = JSON.parse(dataLine.slice(6))

                switch (event) {
                  case "thinking":
                    // 后端发送的思考步骤，直接追加
                    thinkingSteps = [...thinkingSteps, data.message]
                    set({ currentThinking: thinkingSteps })
                    break
                  case "status":
                    // 兼容旧格式
                    thinkingSteps = [...thinkingSteps, data.message]
                    set({ currentThinking: thinkingSteps })
                    break
                  case "tool_call":
                    // 工具调用信息
                    toolCalls = [...toolCalls, data]
                    break
                  case "tool_complete":
                    // 工具完成（旧格式兼容）
                    thinkingSteps = [
                      ...thinkingSteps,
                      `✅ 工具执行完成: ${data.tools.join(", ")}`,
                    ]
                    set({ currentThinking: thinkingSteps })
                    break
                  case "generating":
                    // 开始生成回复
                    thinkingSteps = [...thinkingSteps, "✍️ 正在生成回复..."]
                    set({ currentThinking: thinkingSteps })
                    break
                  case "token":
                    responseText += data.content
                    set((state) => ({
                      messages: state.messages.map((msg) =>
                        msg.id === streamingId
                          ? {
                              ...msg,
                              content: responseText,
                              thinking: thinkingSteps,
                              toolCalls,
                            }
                          : msg
                      ),
                    }))
                    break
                  case "done":
                    // 检查是否需要 HITL 确认
                    const needsConfirm = data.require_human_confirm && data.tool_calls?.length > 0
                    const confirmTool = needsConfirm && data.tool_calls?.length > 0
                      ? data.tool_calls[data.tool_calls.length - 1]
                      : null

                    set((state) => ({
                      messages: state.messages.map((msg) =>
                        msg.id === streamingId
                          ? {
                              ...msg,
                              content: data.response,
                              thinking: thinkingSteps,
                              toolCalls: data.tool_calls,
                              isStreaming: false,
                            }
                          : msg
                      ),
                      isStreaming: false,
                      streamingMessageId: null,
                      currentThinking: [],
                      pendingConfirmation: confirmTool
                        ? { messageId: streamingId, toolName: confirmTool.name, args: confirmTool.args }
                        : null,
                      frustrationScore: data.frustration_score || 0,
                      encouragementMessages: data.encouragement_messages || [],
                    }))
                    break
                  case "error":
                    set((state) => ({
                      messages: state.messages.map((msg) =>
                        msg.id === streamingId
                          ? {
                              ...msg,
                              content: `❌ 错误: ${data.message}`,
                              isStreaming: false,
                            }
                          : msg
                      ),
                      isStreaming: false,
                      streamingMessageId: null,
                      currentThinking: [],
                    }))
                    break
                }
              }
            }
          }
        }
      }
    } catch (error) {
      set((state) => ({
        messages: state.messages.map((msg) =>
          msg.id === streamingId
            ? {
                ...msg,
                content: `连接失败：${error instanceof Error ? error.message : "未知错误"}\n\n请确保后端服务已启动`,
                isStreaming: false,
              }
            : msg
        ),
        isStreaming: false,
        streamingMessageId: null,
        currentThinking: [],
      }))
    }

    // 刷新对话列表（更新标题）
    get().loadConversations()
  },

  regenerateMessage: async (messageId: string) => {
    const { messages } = get()
    const idx = messages.findIndex((m) => m.id === messageId)
    if (idx <= 0) return

    // 找到该 AI 消息前的用户消息
    const prevUserMsg = messages[idx - 1]
    if (prevUserMsg.role !== "user") return

    // 删除原 AI 消息
    set((state) => ({
      messages: state.messages.filter((m) => m.id !== messageId),
    }))

    // 重新发送
    await get().sendMessage(prevUserMsg.content)
  },

  setMessageFeedback: (messageId: string, feedback: 1 | -1 | null) => {
    const { currentConversationId } = get()
    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === messageId ? { ...m, feedback } : m
      ),
    }))
    if (currentConversationId) {
      setMessageFeedback(currentConversationId, messageId, feedback).catch(() => {})
    }
  },

  loadSets: async () => {
    try {
      const sets = await listSets()
      set({ sets })
    } catch {
      // ignore
    }
  },

  setCurrentSet: async (setId: string) => {
    try {
      const set = await getSet(setId)
      set({ currentSet: set })
      // 更新对话的 set_id
      const { currentConversationId } = get()
      if (currentConversationId) {
        await updateConversation(currentConversationId, { set_id: setId }).catch(() => {})
      }
    } catch {
      // ignore
    }
  },

  updateSetProgress: async (step: number) => {
    const { currentSet } = get()
    if (!currentSet) return
    try {
      const updated = await updateProgress(currentSet.set_id, step)
      set({ currentSet: updated })
    } catch {
      // ignore
    }
  },

  confirmAction: (messageId: string) => {
    const { pendingConfirmation } = get()
    if (!pendingConfirmation || pendingConfirmation.messageId !== messageId) return
    // 清除确认状态，在实际项目中这里会通知后端继续执行
    set({ pendingConfirmation: null })
  },

  cancelAction: (messageId: string) => {
    const { pendingConfirmation } = get()
    if (!pendingConfirmation || pendingConfirmation.messageId !== messageId) return
    set({ pendingConfirmation: null })
  },
}))
