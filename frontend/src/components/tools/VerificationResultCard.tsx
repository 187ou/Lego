/** 成品验收结果卡片 */

import { Badge } from "../ui/badge"
import { CheckCircle, AlertTriangle, XCircle } from "lucide-react"
import { cn } from "../../lib/utils"

interface VerificationResultCardProps {
  data: {
    similarity?: number
    verdict?: string
    details?: string
    warning?: string
  }
  userImage?: string
}

const VerificationResultCard: React.FC<VerificationResultCardProps> = ({
  data,
  userImage,
}) => {
  const { similarity = 0, verdict = "unknown", details, warning } = data

  if (warning) {
    return (
      <div className="rounded-lg border border-yellow-200 bg-yellow-50 dark:border-yellow-800 dark:bg-yellow-950 p-3 my-2 text-sm">
        <span className="text-yellow-700 dark:text-yellow-300">⚠️ {warning}</span>
      </div>
    )
  }

  const verdictConfig = {
    pass: {
      icon: CheckCircle,
      label: "通过",
      color: "text-green-600 dark:text-green-400",
      bg: "bg-green-50 dark:bg-green-950",
      border: "border-green-200 dark:border-green-800",
      badge: "success" as const,
    },
    review: {
      icon: AlertTriangle,
      label: "存疑",
      color: "text-yellow-600 dark:text-yellow-400",
      bg: "bg-yellow-50 dark:bg-yellow-950",
      border: "border-yellow-200 dark:border-yellow-800",
      badge: "warning" as const,
    },
    fail: {
      icon: XCircle,
      label: "驳回",
      color: "text-red-600 dark:text-red-400",
      bg: "bg-red-50 dark:bg-red-950",
      border: "border-red-200 dark:border-red-800",
      badge: "destructive" as const,
    },
  }

  const config = verdictConfig[verdict as keyof typeof verdictConfig] || verdictConfig.review
  const Icon = config.icon
  const percentage = Math.round(similarity * 100)

  return (
    <div className={cn("rounded-lg border p-4 my-2", config.bg, config.border)}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Icon className={cn("h-5 w-5", config.color)} />
          <span className="font-medium">成品验收结果</span>
          <Badge variant={config.badge}>{config.label}</Badge>
        </div>
        <div className={cn("text-2xl font-bold", config.color)}>{percentage}%</div>
      </div>

      {/* 相似度环形进度 */}
      <div className="flex items-center gap-4 mb-3">
        <div className="relative w-20 h-20 flex-shrink-0">
          <svg className="w-20 h-20 -rotate-90" viewBox="0 0 36 36">
            <path
              className="text-muted-foreground/20"
              stroke="currentColor"
              strokeWidth="3"
              fill="none"
              d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
            />
            <path
              className={config.color}
              stroke="currentColor"
              strokeWidth="3"
              strokeLinecap="round"
              fill="none"
              strokeDasharray={`${percentage}, 100`}
              d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xs font-medium">相似度</span>
          </div>
        </div>
        <div className="flex-1">
          <p className="text-sm text-foreground">{details}</p>
        </div>
      </div>

      {/* 图片对比 */}
      {userImage && (
        <div className="flex gap-3 mt-3">
          <div className="flex-1 text-center">
            <img
              src={userImage}
              alt="用户成品"
              className="w-full h-24 object-cover rounded-md border"
            />
            <span className="text-xs text-muted-foreground mt-1 block">你的成品</span>
          </div>
          <div className="flex-1 text-center">
            <div className="w-full h-24 rounded-md border bg-muted flex items-center justify-center">
              <span className="text-xs text-muted-foreground">官方参考</span>
            </div>
            <span className="text-xs text-muted-foreground mt-1 block">官方渲染</span>
          </div>
        </div>
      )}
    </div>
  )
}

export default VerificationResultCard
