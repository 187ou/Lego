/** 进度追踪器 */

import { Progress } from "../ui/progress"
import { useChatStore } from "../../store/chatStore"
import { cn } from "../../lib/utils"
import { Trophy } from "lucide-react"

const ProgressTracker: React.FC = () => {
  const currentSet = useChatStore((s) => s.currentSet)
  const updateSetProgress = useChatStore((s) => s.updateSetProgress)

  if (!currentSet || currentSet.total_steps === 0) {
    return null
  }

  const percentage = Math.round((currentSet.current_step / currentSet.total_steps) * 100)

  const handleStepChange = (step: number) => {
    updateSetProgress(step)
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Trophy className="h-3.5 w-3.5 text-lego-yellow" />
          <span className="text-xs font-medium">拼搭进度</span>
        </div>
        <span className="text-xs text-muted-foreground">
          {currentSet.current_step}/{currentSet.total_steps} 步
        </span>
      </div>

      <Progress value={percentage} className="h-2" />

      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{percentage}% 完成</span>
        <div className="flex gap-1">
          <button
            onClick={() => handleStepChange(Math.max(0, currentSet.current_step - 1))}
            className="px-1.5 py-0.5 rounded hover:bg-muted transition"
            disabled={currentSet.current_step <= 0}
          >
            -1
          </button>
          <button
            onClick={() =>
              handleStepChange(Math.min(currentSet.total_steps, currentSet.current_step + 1))
            }
            className="px-1.5 py-0.5 rounded hover:bg-muted transition"
            disabled={currentSet.current_step >= currentSet.total_steps}
          >
            +1
          </button>
        </div>
      </div>
    </div>
  )
}

export default ProgressTracker
