/** 消息气泡组件 */

import { useState } from "react"
import { Avatar } from "../ui/avatar"
import { Tooltip } from "../ui/tooltip"
import { cn } from "../../lib/utils"
import { Copy, RefreshCw, ThumbsUp, ThumbsDown, Check } from "lucide-react"
import type { Message } from "../../types"
import ThinkingBox from "./ThinkingBox"
import ToolResultCard from "./ToolResultCard"
import { useChatStore } from "../../store/chatStore"

interface MessageBubbleProps {
  message: Message
}

const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const { role, content, imageUrl, toolCalls, thinking, isStreaming, feedback, id } = message
  const isUser = role === "user"
  const regenerateMessage = useChatStore((s) => s.regenerateMessage)
  const setMessageFeedback = useChatStore((s) => s.setMessageFeedback)
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleRegenerate = () => {
    if (!isUser) {
      regenerateMessage(id)
    }
  }

  const handleFeedback = (type: 1 | -1) => {
    const newFeedback = feedback === type ? null : type
    setMessageFeedback(id, newFeedback)
  }

  return (
    <div
      className={cn(
        "flex gap-3 max-w-[85%] animate-fade-in",
        isUser ? "self-end flex-row-reverse" : "self-start"
      )}
    >
      <Avatar
        className={cn(
          "flex-shrink-0",
          isUser ? "bg-lego-blue" : "bg-lego-yellow"
        )}
      >
        <span>{isUser ? "👤" : "🤖"}</span>
      </Avatar>

      <div className="flex flex-col gap-1 min-w-0">
        {/* 思考过程 */}
        {!isUser && thinking && thinking.length > 0 && (
          <ThinkingBox steps={thinking} isLive={isStreaming} />
        )}

        {/* 消息气泡 */}
        <div
          className={cn(
            "rounded-2xl px-4 py-3 shadow-sm",
            isUser
              ? "bg-lego-blue text-white rounded-br-md"
              : "bg-card border rounded-bl-md",
            isStreaming && !content && "min-w-[60px]"
          )}
        >
          {/* 图片 */}
          {imageUrl && (
            <img
              src={imageUrl}
              alt="上传的图片"
              className="max-w-[200px] max-h-[200px] rounded-lg mb-2 cursor-pointer hover:opacity-90 transition"
              onClick={() => window.open(imageUrl, "_blank")}
            />
          )}

          {/* 内容 */}
          {content && (
            <div className="text-sm leading-relaxed whitespace-pre-wrap">{content}</div>
          )}

          {/* 流式指示器 */}
          {isStreaming && !content && (
            <div className="flex gap-1 py-1">
              <span className="w-2 h-2 bg-current rounded-full animate-bounce" />
              <span className="w-2 h-2 bg-current rounded-full animate-bounce [animation-delay:0.2s]" />
              <span className="w-2 h-2 bg-current rounded-full animate-bounce [animation-delay:0.4s]" />
            </div>
          )}
        </div>

        {/* 工具结果卡片 */}
        {!isUser && toolCalls && toolCalls.length > 0 && (
          <ToolResultCard toolCalls={toolCalls} userImage={imageUrl} />
        )}

        {/* 消息操作栏 */}
        {!isStreaming && (
          <div
            className={cn(
              "flex items-center gap-1 px-1",
              isUser ? "self-end" : "self-start"
            )}
          >
            <span className="text-[10px] text-muted-foreground mr-2">
              {new Date(message.timestamp).toLocaleTimeString()}
            </span>

            {/* 复制 */}
            {content && (
              <Tooltip content={copied ? "已复制" : "复制"}>
                <button
                  onClick={handleCopy}
                  className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition"
                >
                  {copied ? (
                    <Check className="h-3.5 w-3.5" />
                  ) : (
                    <Copy className="h-3.5 w-3.5" />
                  )}
                </button>
              </Tooltip>
            )}

            {/* 重新生成（仅 AI 消息） */}
            {!isUser && (
              <Tooltip content="重新生成">
                <button
                  onClick={handleRegenerate}
                  className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                </button>
              </Tooltip>
            )}

            {/* 反馈（仅 AI 消息） */}
            {!isUser && (
              <>
                <Tooltip content="有帮助">
                  <button
                    onClick={() => handleFeedback(1)}
                    className={cn(
                      "p-1 rounded hover:bg-muted transition",
                      feedback === 1
                        ? "text-green-500"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    <ThumbsUp className="h-3.5 w-3.5" />
                  </button>
                </Tooltip>
                <Tooltip content="没帮助">
                  <button
                    onClick={() => handleFeedback(-1)}
                    className={cn(
                      "p-1 rounded hover:bg-muted transition",
                      feedback === -1
                        ? "text-red-500"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    <ThumbsDown className="h-3.5 w-3.5" />
                  </button>
                </Tooltip>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default MessageBubble
