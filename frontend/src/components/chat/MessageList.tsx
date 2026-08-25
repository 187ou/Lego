/** 消息列表组件 - 优化滚动和流式体验 */

import { useEffect, useRef } from "react"
import { ScrollArea } from "../ui/scroll-area"
import MessageBubble from "./MessageBubble"
import { useChatStore } from "../../store/chatStore"

const MessageList: React.FC = () => {
  const messages = useChatStore((s) => s.messages)
  const isStreaming = useChatStore((s) => s.isStreaming)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // 自动滚动到底部（流式输出时实时跟随）
  useEffect(() => {
    if (isStreaming) {
      // 流式时立即滚动（无动画，避免抖动）
      messagesEndRef.current?.scrollIntoView({ behavior: "instant" })
    } else {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
    }
  }, [messages, isStreaming])

  return (
    <ScrollArea className="flex-1 px-4 py-6">
      <div className="max-w-3xl mx-auto flex flex-col gap-6">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        <div ref={messagesEndRef} className="h-1" />
      </div>
    </ScrollArea>
  )
}

export default MessageList
