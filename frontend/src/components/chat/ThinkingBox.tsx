/** 思考过程展示组件 - 支持折叠 + 实时流式动画 */

import { useState } from "react"
import { cn } from "../../lib/utils"
import { ChevronDown, ChevronRight, Brain, Loader2 } from "lucide-react"

interface ThinkingBoxProps {
  steps: string[]
  isLive?: boolean
  defaultExpanded?: boolean
}

const ThinkingBox: React.FC<ThinkingBoxProps> = ({
  steps,
  isLive = false,
  defaultExpanded = true,
}) => {
  const [expanded, setExpanded] = useState(defaultExpanded)

  if (steps.length === 0 && !isLive) return null

  return (
    <div
      className={cn(
        "rounded-xl border overflow-hidden text-sm",
        isLive ? "bg-lego-yellow/5 border-lego-yellow/30" : "bg-muted/50 border-border"
      )}
    >
      {/* 头部 - 可点击折叠 */}
      <button
        onClick={() => setExpanded(!expanded)}
        className={cn(
          "w-full flex items-center gap-2 px-3 py-2 text-left transition-colors",
          isLive
            ? "hover:bg-lego-yellow/10 text-lego-yellow"
            : "hover:bg-muted text-muted-foreground"
        )}
      >
        {isLive ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Brain className="h-4 w-4" />
        )}
        <span className="font-medium flex-1">
          {isLive ? "思考中..." : "思考过程"}
        </span>
        <span className="text-xs opacity-60">{steps.length} 步</span>
        {expanded ? (
          <ChevronDown className="h-4 w-4" />
        ) : (
          <ChevronRight className="h-4 w-4" />
        )}
      </button>

      {/* 思考步骤列表 */}
      {expanded && (
        <div className="px-3 pb-3 space-y-1.5 animate-fade-in">
          {steps.map((step, i) => (
            <div
              key={i}
              className={cn(
                "flex items-start gap-2 py-1.5 pl-3 border-l-2 animate-slide-in",
                isLive && i === steps.length - 1
                  ? "border-lego-yellow text-foreground"
                  : "border-muted-foreground/30 text-muted-foreground"
              )}
              style={{ animationDelay: `${i * 50}ms` }}
            >
              <span className="text-xs mt-0.5 flex-shrink-0 opacity-50">
                {i + 1}.
              </span>
              <span className="leading-relaxed">{step}</span>
            </div>
          ))}

          {/* 流式加载指示器 */}
          {isLive && (
            <div className="flex items-center gap-2 pl-3 py-1 text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" />
              <span className="text-xs">正在处理...</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default ThinkingBox
