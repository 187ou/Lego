/** 图片解析结果卡片 */

import { Badge } from "../ui/badge"
import { AlertTriangle } from "lucide-react"
import { cn } from "../../lib/utils"

interface ImageParseCardProps {
  data: {
    parts?: { name: string; color: string; quantity: number }[]
    colors?: string[]
    step_number?: number | null
    confidence?: number
    needs_retry?: boolean
  }
}

const ImageParseCard: React.FC<ImageParseCardProps> = ({ data }) => {
  const { parts = [], colors = [], step_number, confidence = 0, needs_retry } = data

  return (
    <div className="rounded-lg border bg-card p-4 my-2">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-lg">📷</span>
        <span className="font-medium">图片识别结果</span>
        {confidence > 0 && (
          <Badge
            variant={confidence >= 0.7 ? "success" : "warning"}
            className="ml-auto"
          >
            置信度 {Math.round(confidence * 100)}%
          </Badge>
        )}
      </div>

      {needs_retry && (
        <div className="flex items-center gap-2 p-2 rounded-md bg-yellow-50 dark:bg-yellow-950 border border-yellow-200 dark:border-yellow-800 mb-3 text-sm">
          <AlertTriangle className="h-4 w-4 text-yellow-600" />
          <span className="text-yellow-700 dark:text-yellow-300">
            图片不够清晰，请重新拍摄或描述零件名称
          </span>
        </div>
      )}

      {/* 识别出的零件 */}
      {parts.length > 0 && (
        <div className="mb-3">
          <div className="text-xs text-muted-foreground mb-2">识别零件</div>
          <div className="space-y-1">
            {parts.map((part, i) => (
              <div
                key={i}
                className="flex items-center justify-between py-1.5 px-2 rounded bg-muted/50 text-sm"
              >
                <span>{part.name}</span>
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="text-xs">
                    {part.color}
                  </Badge>
                  <span className="text-xs text-muted-foreground">x{part.quantity}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 颜色标签 */}
      {colors.length > 0 && (
        <div className="mb-3">
          <div className="text-xs text-muted-foreground mb-2">颜色</div>
          <div className="flex flex-wrap gap-1">
            {colors.map((color, i) => (
              <Badge key={i} variant="secondary" className="text-xs">
                {color}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* 步骤号 */}
      {step_number && (
        <div className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">步骤号:</span>
          <Badge>第 {step_number} 步</Badge>
        </div>
      )}
    </div>
  )
}

export default ImageParseCard
