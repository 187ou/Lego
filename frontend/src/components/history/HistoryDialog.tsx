/** 历史对话浏览弹窗 */

import { useState, useMemo } from "react"
import { Dialog, DialogTitle } from "../ui/dialog"
import { ScrollArea } from "../ui/scroll-area"
import { useChatStore } from "../../store/chatStore"
import { Search, MessageSquare, Trash2, Clock, ChevronRight } from "lucide-react"
import { cn } from "../../lib/utils"
import { Button } from "../ui/button"
import type { ConversationMeta } from "../../types"

interface HistoryDialogProps {
  open: boolean
  onClose: () => void
}

interface ConversationWithPreview extends ConversationMeta {
  preview?: string
  messageCount?: number
}

const HistoryDialog: React.FC<HistoryDialogProps> = ({ open, onClose }) => {
  const [searchQuery, setSearchQuery] = useState("")
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const conversations = useChatStore((s) => s.conversations)
  const currentConversationId = useChatStore((s) => s.currentConversationId)
  const switchConversation = useChatStore((s) => s.switchConversation)
  const deleteConversation = useChatStore((s) => s.deleteConversation)
  const [conversationPreviews, setConversationPreviews] = useState<Record<string, { preview: string; count: number }>>({})

  // 加载对话预览
  const loadPreview = async (convId: string) => {
    if (conversationPreviews[convId]) return
    try {
      const { getConversation } = await import("../../lib/api")
      const data = await getConversation(convId)
      const firstUserMsg = data.messages.find((m: { role: string }) => m.role === "user")
      setConversationPreviews((prev) => ({
        ...prev,
        [convId]: {
          preview: firstUserMsg?.content?.slice(0, 60) || "空对话",
          count: data.messages.length,
        },
      }))
    } catch {
      setConversationPreviews((prev) => ({
        ...prev,
        [convId]: { preview: "无法加载", count: 0 },
      }))
    }
  }

  // 过滤对话
  const filteredConversations = useMemo(() => {
    if (!searchQuery.trim()) return conversations
    const q = searchQuery.toLowerCase()
    return conversations.filter(
      (c) => c.title.toLowerCase().includes(q) || c.set_id.toLowerCase().includes(q)
    )
  }, [conversations, searchQuery])

  // 按日期分组
  const groupedConversations = useMemo(() => {
    const groups: Record<string, typeof filteredConversations> = {}
    const today = new Date().toDateString()
    const yesterday = new Date(Date.now() - 86400000).toDateString()

    filteredConversations.forEach((conv) => {
      const date = new Date(conv.updated_at)
      const dateStr = date.toDateString()
      let group: string

      if (dateStr === today) group = "今天"
      else if (dateStr === yesterday) group = "昨天"
      else if (Date.now() - date.getTime() < 7 * 86400000) group = "最近 7 天"
      else group = "更早"

      if (!groups[group]) groups[group] = []
      groups[group].push(conv)
    })

    return groups
  }, [filteredConversations])

  const handleSelectConversation = (id: string) => {
    setSelectedId(id)
    loadPreview(id)
  }

  const handleOpenConversation = (id: string) => {
    switchConversation(id)
    onClose()
  }

  const handleDelete = (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    deleteConversation(id)
    if (selectedId === id) setSelectedId(null)
  }

  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
  }

  return (
    <Dialog open={open} onClose={onClose}>
      <DialogTitle>历史对话</DialogTitle>

      <div className="flex h-[500px] -mx-6 -mb-6 mt-4">
        {/* 左侧对话列表 */}
        <div className="w-80 border-r flex flex-col">
          {/* 搜索框 */}
          <div className="p-3 border-b">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="搜索对话..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-2 text-sm rounded-md border border-input bg-background focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
          </div>

          {/* 对话列表 */}
          <ScrollArea className="flex-1">
            {Object.entries(groupedConversations).map(([group, convs]) => (
              <div key={group}>
                <div className="px-3 py-2 text-xs font-medium text-muted-foreground sticky top-0 bg-background/95 backdrop-blur">
                  {group}
                </div>
                {convs.map((conv) => (
                  <div
                    key={conv.id}
                    onClick={() => handleSelectConversation(conv.id)}
                    className={cn(
                      "px-3 py-2.5 cursor-pointer border-l-2 transition-all",
                      selectedId === conv.id
                        ? "bg-muted border-l-lego-blue"
                        : "border-l-transparent hover:bg-muted/50"
                    )}
                  >
                    <div className="flex items-start gap-2">
                      <MessageSquare className="h-4 w-4 mt-0.5 text-muted-foreground flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium truncate">{conv.title}</span>
                          <span className="text-[10px] text-muted-foreground ml-2 flex-shrink-0">
                            {formatTime(conv.updated_at)}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 mt-0.5">
                          {conv.set_id && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                              {conv.set_id}
                            </span>
                          )}
                          <span className="text-[10px] text-muted-foreground">
                            {conversationPreviews[conv.id]?.messageCount ?? "..."} 条消息
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ))}

            {filteredConversations.length === 0 && (
              <div className="p-8 text-center text-sm text-muted-foreground">
                {searchQuery ? "未找到匹配的对话" : "暂无历史对话"}
              </div>
            )}
          </ScrollArea>
        </div>

        {/* 右侧预览 */}
        <div className="flex-1 flex flex-col bg-muted/30">
          {selectedId ? (
            <>
              {/* 预览头部 */}
              <div className="p-4 border-b bg-background">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-medium">
                      {conversations.find((c) => c.id === selectedId)?.title}
                    </h3>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      <Clock className="h-3 w-3 inline mr-1" />
                      {conversations.find((c) => c.id === selectedId)?.updated_at &&
                        new Date(
                          conversations.find((c) => c.id === selectedId)!.updated_at
                        ).toLocaleString()}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={(e) => handleDelete(e, selectedId)}
                    >
                      <Trash2 className="h-3.5 w-3.5 mr-1" />
                      删除
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => handleOpenConversation(selectedId)}
                      disabled={selectedId === currentConversationId}
                    >
                      {selectedId === currentConversationId ? "当前对话" : "打开"}
                      {selectedId !== currentConversationId && (
                        <ChevronRight className="h-3.5 w-3.5 ml-1" />
                      )}
                    </Button>
                  </div>
                </div>
              </div>

              {/* 消息预览 */}
              <ScrollArea className="flex-1 p-4">
                <ConversationPreview convId={selectedId} />
              </ScrollArea>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-muted-foreground">
              <div className="text-center">
                <MessageSquare className="h-12 w-12 mx-auto mb-3 opacity-30" />
                <p className="text-sm">选择一个对话查看详情</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </Dialog>
  )
}

// 对话消息预览组件
const ConversationPreview: React.FC<{ convId: string }> = ({ convId }) => {
  const [messages, setMessages] = useState<Array<{
    id: string
    role: string
    content: string
    timestamp: string
  }>>([])
  const [loading, setLoading] = useState(true)

  useMemo(() => {
    let cancelled = false
    const load = async () => {
      setLoading(true)
      try {
        const { getConversation } = await import("../../lib/api")
        const data = await getConversation(convId)
        if (!cancelled) {
          setMessages(data.messages)
        }
      } catch {
        if (!cancelled) setMessages([])
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [convId])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="flex gap-1">
          <span className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" />
          <span className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce [animation-delay:0.2s]" />
          <span className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce [animation-delay:0.4s]" />
        </div>
      </div>
    )
  }

  if (messages.length === 0) {
    return (
      <div className="text-center text-sm text-muted-foreground py-8">
        该对话暂无消息
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={cn(
            "flex gap-2",
            msg.role === "user" ? "flex-row-reverse" : "flex-row"
          )}
        >
          <div
            className={cn(
              "rounded-lg px-3 py-2 text-sm max-w-[80%]",
              msg.role === "user"
                ? "bg-lego-blue text-white rounded-br-sm"
                : "bg-card border rounded-bl-sm"
            )}
          >
            {msg.content}
          </div>
        </div>
      ))}
    </div>
  )
}

export default HistoryDialog
