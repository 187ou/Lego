/** 步骤列表侧边栏 */

import { useBuilder3dStore } from "@/store/builder3dStore"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Check, Circle } from "lucide-react"

export function StepSidebar() {
  const { model, currentStep, goToStep } = useBuilder3dStore()

  return (
    <div className="absolute left-4 top-1/2 -translate-y-1/2 w-56 bg-background/90 backdrop-blur-md rounded-lg border shadow-lg overflow-hidden">
      {/* 标题 */}
      <div className="px-3 py-2 border-b bg-muted/50">
        <p className="text-xs font-medium text-muted-foreground">拼装步骤</p>
      </div>

      {/* 步骤列表 */}
      <ScrollArea className="max-h-80">
        <div className="p-1">
          {model.steps.map((step) => {
            const isCompleted = step.stepNumber < currentStep
            const isCurrent = step.stepNumber === currentStep

            return (
              <button
                key={step.stepNumber}
                onClick={() => goToStep(step.stepNumber)}
                className={`w-full flex items-center gap-2 px-2 py-2 rounded text-left text-xs transition-colors ${
                  isCurrent
                    ? "bg-primary/10 text-primary font-medium"
                    : isCompleted
                    ? "text-muted-foreground hover:bg-muted/50"
                    : "hover:bg-muted/50"
                }`}
              >
                {/* 状态图标 */}
                <div className="flex-shrink-0">
                  {isCompleted ? (
                    <Check className="h-4 w-4 text-green-500" />
                  ) : isCurrent ? (
                    <Circle className="h-4 w-4 fill-primary text-primary" />
                  ) : (
                    <Circle className="h-4 w-4 text-muted-foreground/50" />
                  )}
                </div>

                {/* 步骤信息 */}
                <div className="flex-1 min-w-0">
                  <p className="truncate">
                    步骤 {step.stepNumber}
                  </p>
                  <p className="text-[10px] text-muted-foreground truncate">
                    {step.bricksToAdd.length} 块积木
                  </p>
                </div>
              </button>
            )
          })}
        </div>
      </ScrollArea>
    </div>
  )
}
