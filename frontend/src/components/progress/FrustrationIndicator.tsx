/** 挫折感知指示器 - 接入真实数据 */

import { useState } from "react"
import { cn } from "../../lib/utils"
import { Heart, TrendingUp, Sparkles } from "lucide-react"
import { useChatStore } from "../../store/chatStore"

const FrustrationIndicator: React.FC = () => {
  const [expanded, setExpanded] = useState(false)
  const frustrationScore = useChatStore((s) => s.frustrationScore)
  const encouragementMessages = useChatStore((s) => s.encouragementMessages)
  const currentSet = useChatStore((s) => s.currentSet)

  const getEmoji = (score: number) => {
    if (score < 30) return "😊"
    if (score < 60) return "😐"
    return "😤"
  }

  const getMessage = (score: number) => {
    if (score < 30) return "状态不错，继续加油！"
    if (score < 60) return "有点卡住了？需要帮忙吗？"
    return "别急，我来帮你拆解一下"
  }

  const progressPercent = currentSet && currentSet.total_steps > 0
    ? Math.round((currentSet.current_step / currentSet.total_steps) * 100)
    : 0

  return (
    <div
      className={cn(
        "rounded-lg border bg-muted/50 p-2.5 cursor-pointer transition-all",
        expanded && "bg-muted"
      )}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center gap-2">
        <Heart className="h-3.5 w-3.5 text-lego-red" />
        <span className="text-xs font-medium flex-1">状态感知</span>
        <span className="text-lg leading-none">{getEmoji(frustrationScore)}</span>
      </div>

      {expanded && (
        <div className="mt-2 pt-2 border-t space-y-2 animate-fade-in">
          <p className="text-xs text-muted-foreground">{getMessage(frustrationScore)}</p>

          {/* 进度 */}
          {currentSet && currentSet.total_steps > 0 && (
            <div className="flex items-center gap-2">
              <TrendingUp className="h-3 w-3 text-lego-green" />
              <span className="text-xs">
                已完成 <span className="font-medium">{progressPercent}%</span> ({currentSet.current_step}/{currentSet.total_steps} 步)
              </span>
            </div>
          )}

          {/* 挫折分数指示 */}
          <div className="flex items-center gap-2">
            <div className="flex-1 h-1.5 rounded-full bg-muted-foreground/20 overflow-hidden">
              <div
                className={cn(
                  "h-full rounded-full transition-all duration-500",
                  frustrationScore < 30 ? "bg-green-500" :
                  frustrationScore < 60 ? "bg-yellow-500" : "bg-red-500"
                )}
                style={{ width: `${frustrationScore}%` }}
              />
            </div>
            <span className="text-[10px] text-muted-foreground">{frustrationScore}/100</span>
          </div>

          {/* 安抚话术 */}
          {encouragementMessages.length > 0 && (
            <div className="rounded-md bg-lego-yellow/10 border border-lego-yellow/20 p-2 space-y-1">
              {encouragementMessages.map((msg, i) => (
                <p key={i} className="text-xs text-foreground flex items-start gap-1">
                  <Sparkles className="h-3 w-3 text-lego-yellow flex-shrink-0 mt-0.5" />
                  {msg}
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default FrustrationIndicator
