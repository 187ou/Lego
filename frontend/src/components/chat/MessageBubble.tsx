/** 消息气泡组件 - 集成流式思考过程 */

import { useState } from "react"
import { Avatar } from "../ui/avatar"
import { Tooltip } from "../ui/tooltip"
import { cn } from "../../lib/utils"
import { Copy, RefreshCw, ThumbsUp, ThumbsDown, Check, Image as ImageIcon } from "lucide-react"
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
  const [imageExpanded, setImageExpanded] = useState(false)

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

  // 是否有思考过程或工具调用
  const hasThinking = thinking && thinking.length > 0
  const hasToolCalls = toolCalls && toolCalls.length > 0

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

      <div className="flex flex-col gap-1.5 min-w-0 flex-1">
        {/* 用户消息 */}
        {isUser && (
          <div
            className={cn(
              "rounded-2xl px-4 py-3 shadow-sm bg-lego-blue text-white rounded-br-md"
            )}
          >
            {imageUrl && (
              <div className="relative mb-2">
                <img
                  src={imageUrl}
                  alt="上传的图片"
                  className={cn(
                    "rounded-lg cursor-pointer hover:opacity-90 transition",
                    imageExpanded ? "max-w-full max-h-[400px]" : "max-w-[200px] max-h-[200px]"
                  )}
                  onClick={() => setImageExpanded(!imageExpanded)}
                />
                <div className="absolute bottom-2 right-2 bg-black/50 rounded-full p-1">
                  <ImageIcon className="h-3 w-3 text-white" />
                </div>
              </div>
            )}
            {content && (
              <div className="text-sm leading-relaxed whitespace-pre-wrap">{content}</div>
            )}
          </div>
        )}

        {/* AI 消息 */}
        {!isUser && (
          <>
            {/* 思考过程（流式展示） */}
            {(hasThinking || isStreaming) && (
              <ThinkingBox steps={thinking || []} isLive={isStreaming} />
            )}

            {/* 消息内容气泡 */}
            {(content || isStreaming) && (
              <div
                className={cn(
                  "rounded-2xl px-4 py-3 shadow-sm bg-card border rounded-bl-md",
                  isStreaming && !content && "min-w-[80px]"
                )}
              >
                {/* 图片 */}
                {imageUrl && (
                  <div className="relative mb-2">
                    <img
                      src={imageUrl}
                      alt="上传的图片"
                      className={cn(
                        "rounded-lg cursor-pointer hover:opacity-90 transition",
                        imageExpanded ? "max-w-full max-h-[400px]" : "max-w-[200px] max-h-[200px]"
                      )}
                      onClick={() => setImageExpanded(!imageExpanded)}
                    />
                  </div>
                )}

                {/* 流式内容 */}
                {content && (
                  <div className="text-sm leading-relaxed whitespace-pre-wrap">
                    {content}
                    {isStreaming && (
                      <span className="inline-block w-2 h-4 bg-lego-yellow animate-pulse ml-0.5 align-middle" />
                    )}
                  </div>
                )}

                {/* 纯流式指示器（无内容时） */}
                {isStreaming && !content && (
                  <div className="flex items-center gap-2">
                    <div className="flex gap-1">
                      <span className="w-2 h-2 bg-lego-yellow rounded-full animate-bounce" />
                      <span className="w-2 h-2 bg-lego-yellow rounded-full animate-bounce [animation-delay:0.2s]" />
                      <span className="w-2 h-2 bg-lego-yellow rounded-full animate-bounce [animation-delay:0.4s]" />
                    </div>
                    <span className="text-xs text-muted-foreground">正在思考...</span>
                  </div>
                )}
              </div>
            )}

            {/* 工具结果卡片 */}
            {hasToolCalls && (
              <ToolResultCard toolCalls={toolCalls} userImage={imageUrl} />
            )}
          </>
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

            {/* 复制按钮 */}
            {content && (
              <Tooltip content={copied ? "已复制" : "复制"}>
                <span>
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
                </span>
              </Tooltip>
            )}

            {/* 重新生成（仅 AI 消息） */}
            {!isUser && (
              <Tooltip content="重新生成">
                <span>
                  <button
                    onClick={handleRegenerate}
                    className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition"
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                  </button>
                </span>
              </Tooltip>
            )}

            {/* 反馈（仅 AI 消息） */}
            {!isUser && (
              <>
                <Tooltip content="有帮助">
                  <span>
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
                  </span>
                </Tooltip>
                <Tooltip content="没帮助">
                  <span>
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
                  </span>
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
