/** 说明书步骤卡片 */

import { Badge } from "../ui/badge"
import { Button } from "../ui/button"
import { ChevronLeft, ChevronRight, BookOpen } from "lucide-react"
import { useChatStore } from "../../store/chatStore"

interface ManualStepCardProps {
  data: {
    set_id?: string
    step_number?: number
    content?: string
    page_number?: number
    image_url?: string | null
    warning?: string
  }
}

const ManualStepCard: React.FC<ManualStepCardProps> = ({ data }) => {
  const sendMessage = useChatStore((s) => s.sendMessage)
  const { content, step_number, page_number, warning } = data

  if (warning) {
    return (
      <div className="rounded-lg border border-yellow-200 bg-yellow-50 dark:border-yellow-800 dark:bg-yellow-950 p-3 my-2 text-sm">
        <span className="text-yellow-700 dark:text-yellow-300">⚠️ {warning}</span>
      </div>
    )
  }

  const handlePrevStep = () => {
    if (step_number && step_number > 1) {
      sendMessage(`第 ${step_number - 1} 步怎么拼？`)
    }
  }

  const handleNextStep = () => {
    if (step_number) {
      sendMessage(`第 ${step_number + 1} 步怎么拼？`)
    }
  }

  return (
    <div className="rounded-lg border bg-card p-4 my-2">
      <div className="flex items-center gap-2 mb-3">
        <BookOpen className="h-5 w-5 text-lego-blue" />
        <span className="font-medium">说明书步骤</span>
        {step_number && <Badge variant="default">步骤 {step_number}</Badge>}
        {page_number && <Badge variant="outline">第 {page_number} 页</Badge>}
      </div>

      {content && (
        <div className="text-sm leading-relaxed text-foreground mb-4 pl-4 border-l-2 border-lego-blue/30">
          {content}
        </div>
      )}

      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={handlePrevStep}
          disabled={!step_number || step_number <= 1}
        >
          <ChevronLeft className="h-4 w-4 mr-1" />
          上一步
        </Button>
        <Button variant="outline" size="sm" onClick={handleNextStep} disabled={!step_number}>
          下一步
          <ChevronRight className="h-4 w-4 ml-1" />
        </Button>
      </div>
    </div>
  )
}

export default ManualStepCard
