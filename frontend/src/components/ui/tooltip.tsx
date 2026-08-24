import * as React from "react"
import { cn } from "../../lib/utils"

interface TooltipProps {
  content: string
  children: React.ReactNode
  side?: "top" | "bottom" | "left" | "right"
}

const Tooltip: React.FC<TooltipProps> = ({ content, children, side = "top" }) => {
  const [visible, setVisible] = React.useState(false)

  const positionClass = {
    top: "bottom-full left-1/2 -translate-x-1/2 mb-2",
    bottom: "top-full left-1/2 -translate-x-1/2 mt-2",
    left: "right-full top-1/2 -translate-y-1/2 mr-2",
    right: "left-full top-1/2 -translate-y-1/2 ml-2",
  }[side]

  return (
    <div
      className="relative inline-flex"
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
    >
      {children}
      {visible && (
        <div
          className={cn(
            "absolute z-50 px-3 py-1.5 text-xs text-primary-foreground bg-primary rounded-md shadow-lg whitespace-nowrap animate-fade-in",
            positionClass
          )}
        >
          {content}
        </div>
      )}
    </div>
  )
}

export { Tooltip }
