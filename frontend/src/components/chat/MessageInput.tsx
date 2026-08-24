/** 消息输入组件 */

import { useState, useRef, useCallback } from "react"
import { Button } from "../ui/button"
import { Textarea } from "../ui/textarea"
import { ImagePlus, Send, X, Mic, MicOff } from "lucide-react"
import { cn } from "../../lib/utils"
import { useChatStore } from "../../store/chatStore"
import useSpeechInput from "../../hooks/useSpeechInput"

const MessageInput: React.FC = () => {
  const [input, setInput] = useState("")
  const [selectedImage, setSelectedImage] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const isStreaming = useChatStore((s) => s.isStreaming)
  const sendMessage = useChatStore((s) => s.sendMessage)

  const { isListening, isSupported: speechSupported, toggleListening } = useSpeechInput({
    onResult: (text) => setInput((prev) => (prev ? prev + text : text)),
  })

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setSelectedImage(file)
      setImagePreview(URL.createObjectURL(file))
    }
  }

  const clearImage = () => {
    setSelectedImage(null)
    setImagePreview(null)
    if (fileInputRef.current) fileInputRef.current.value = ""
  }

  const handleSend = useCallback(() => {
    if ((!input.trim() && !selectedImage) || isStreaming) return
    sendMessage(input, selectedImage || undefined)
    setInput("")
    clearImage()
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"
    }
  }, [input, selectedImage, isStreaming, sendMessage])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    // 自动调整高度
    const el = e.target
    el.style.height = "auto"
    el.style.height = Math.min(el.scrollHeight, 120) + "px"
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const file = e.dataTransfer.files?.[0]
    if (file && file.type.startsWith("image/")) {
      setSelectedImage(file)
      setImagePreview(URL.createObjectURL(file))
    }
  }

  return (
    <div className="border-t bg-background p-4">
      {/* 图片预览 */}
      {imagePreview && (
        <div className="relative inline-block mb-3">
          <img
            src={imagePreview}
            alt="预览"
            className="h-20 w-20 rounded-lg border-2 border-border object-cover"
          />
          <button
            onClick={clearImage}
            className="absolute -top-2 -right-2 h-5 w-5 rounded-full bg-destructive text-destructive-foreground flex items-center justify-center"
          >
            <X className="h-3 w-3" />
          </button>
        </div>
      )}

      {/* 输入区域 */}
      <div
        className="flex items-end gap-2"
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
      >
        {/* 上传按钮 */}
        <Button
          variant="outline"
          size="icon"
          onClick={() => fileInputRef.current?.click()}
          disabled={isStreaming}
          className="flex-shrink-0"
        >
          <ImagePlus className="h-5 w-5" />
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={handleImageSelect}
          className="hidden"
        />

        {/* 文本输入 */}
        <div className="flex-1 relative">
          <Textarea
            ref={textareaRef}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="输入消息，或拖拽图片到此处..."
            disabled={isStreaming}
            rows={1}
            className="resize-none min-h-[44px] max-h-[120px] pr-12"
          />
          {/* 语音输入按钮 */}
          {speechSupported && (
            <button
              onClick={toggleListening}
              className={cn(
                "absolute right-2 bottom-2 p-1.5 rounded-full transition",
                isListening
                  ? "bg-destructive text-destructive-foreground animate-pulse"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              )}
            >
              {isListening ? (
                <MicOff className="h-4 w-4" />
              ) : (
                <Mic className="h-4 w-4" />
              )}
            </button>
          )}
        </div>

        {/* 发送按钮 */}
        <Button
          onClick={handleSend}
          disabled={isStreaming || (!input.trim() && !selectedImage)}
          className="flex-shrink-0 bg-lego-red hover:bg-lego-red/90"
          size="icon"
        >
          <Send className="h-5 w-5" />
        </Button>
      </div>

      {/* 语音提示 */}
      {isListening && (
        <div className="text-xs text-muted-foreground mt-2 text-center animate-pulse">
          🎤 正在聆听... 点击麦克风停止
        </div>
      )}
    </div>
  )
}

export default MessageInput
