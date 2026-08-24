/** 思考过程展示组件 */

import { cn } from "../../lib/utils"

interface ThinkingBoxProps {
  steps: string[]
  isLive?: boolean
}

const ThinkingBox: React.FC<ThinkingBoxProps> = ({ steps, isLive = false }) => {
  if (steps.length === 0) return null

  return (
    <div
      className={cn(
        "rounded-xl border bg-muted/50 p-3 mb-3 text-sm",
        isLive && "animate-pulse-slow"
      )}
    >
      <div className="font-medium text-foreground mb-2 flex items-center gap-2">
        <span>💭</span>
        <span>{isLive ? "思考中..." : "思考过程"}</span>
      </div>
      {steps.map((step, i) => (
        <div
          key={i}
          className="py-1 pl-3 border-l-2 border-muted-foreground/30 text-muted-foreground animate-slide-in"
        >
          {step}
        </div>
      ))}
    </div>
  )
}

export default ThinkingBox
