/** 零件替代方案卡片 */

import { cn } from "../../lib/utils"
import { Badge } from "../ui/badge"
import { Progress } from "../ui/progress"

interface Alternative {
  name: string
  color: string
  confidence: number
  part_id?: string
}

interface PartAlternativeCardProps {
  data: {
    query?: string
    alternatives?: Alternative[]
    message?: string
    warning?: string
  }
}

const PartAlternativeCard: React.FC<PartAlternativeCardProps> = ({ data }) => {
  const { alternatives, message, warning } = data

  if (warning) {
    return (
      <div className="rounded-lg border border-yellow-200 bg-yellow-50 dark:border-yellow-800 dark:bg-yellow-950 p-3 my-2 text-sm">
        <span className="text-yellow-700 dark:text-yellow-300">⚠️ {warning}</span>
      </div>
    )
  }

  if (!alternatives || alternatives.length === 0) {
    return (
      <div className="rounded-lg border bg-muted/50 p-3 my-2 text-sm text-muted-foreground">
        {message || "未找到替代方案"}
      </div>
    )
  }

  return (
    <div className="rounded-lg border bg-card p-4 my-2">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-lg">🔧</span>
        <span className="font-medium">零件替代方案</span>
        {data.query && <Badge variant="outline">{data.query}</Badge>}
      </div>
      <div className="space-y-3">
        {alternatives.map((alt, i) => (
          <div key={i} className="flex items-center gap-3">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-sm font-medium">{alt.name}</span>
                <Badge variant="secondary" className="text-xs">
                  {alt.color}
                </Badge>
              </div>
              <Progress
                value={alt.confidence * 100}
                className="h-2"
              />
            </div>
            <Badge
              variant={
                alt.confidence >= 0.8
                  ? "success"
                  : alt.confidence >= 0.5
                  ? "warning"
                  : "secondary"
              }
              className="min-w-[60px] justify-center"
            >
              {Math.round(alt.confidence * 100)}%
            </Badge>
          </div>
        ))}
      </div>
    </div>
  )
}

export default PartAlternativeCard
