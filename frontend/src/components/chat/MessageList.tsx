/** 消息列表组件 */

import { useEffect, useRef } from "react"
import { ScrollArea } from "../ui/scroll-area"
import MessageBubble from "./MessageBubble"
import { useChatStore } from "../../store/chatStore"

const MessageList: React.FC = () => {
  const messages = useChatStore((s) => s.messages)
  const isStreaming = useChatStore((s) => s.isStreaming)
  const currentThinking = useChatStore((s) => s.currentThinking)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, currentThinking])

  return (
    <ScrollArea className="flex-1 px-4 py-6">
      <div className="max-w-3xl mx-auto flex flex-col gap-4">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {/* 实时思考过程 */}
        {isStreaming && currentThinking.length > 0 && (
          <div className="flex gap-3 self-start max-w-[85%] animate-fade-in">
            <div className="h-10 w-10 rounded-full bg-lego-yellow flex items-center justify-center flex-shrink-0">
              <span>🤖</span>
            </div>
            <div className="rounded-2xl border bg-card px-4 py-3 shadow-sm rounded-bl-md">
              <div className="space-y-1">
                {currentThinking.map((step, i) => (
                  <div
                    key={i}
                    className="text-sm text-muted-foreground animate-slide-in"
                  >
                    {step}
                  </div>
                ))}
              </div>
              <div className="flex gap-1 py-2 mt-2">
                <span className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" />
                <span className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce [animation-delay:0.2s]" />
                <span className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce [animation-delay:0.4s]" />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>
    </ScrollArea>
  )
}

export default MessageList
