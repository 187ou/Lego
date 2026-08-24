/** Human-in-the-loop 确认对话框 */

import { AlertTriangle, Check, X } from "lucide-react"
import { Button } from "../ui/button"
import { useChatStore } from "../../store/chatStore"

const ConfirmDialog: React.FC = () => {
  const pendingConfirmation = useChatStore((s) => s.pendingConfirmation)
  const confirmAction = useChatStore((s) => s.confirmAction)
  const cancelAction = useChatStore((s) => s.cancelAction)

  if (!pendingConfirmation) return null

  const { messageId, toolName, args } = pendingConfirmation

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="fixed inset-0 bg-black/50" onClick={() => cancelAction(messageId)} />
      <div className="relative z-50 w-full max-w-md rounded-lg bg-card border shadow-xl p-6 animate-fade-in">
        <div className="flex items-center gap-3 mb-4">
          <div className="h-10 w-10 rounded-full bg-yellow-100 dark:bg-yellow-900 flex items-center justify-center">
            <AlertTriangle className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
          </div>
          <div>
            <h3 className="font-semibold">确认执行操作</h3>
            <p className="text-sm text-muted-foreground">此操作需要你的确认</p>
          </div>
        </div>

        <div className="rounded-md bg-muted p-3 mb-4">
          <div className="text-sm font-medium mb-1">工具: {toolName}</div>
          {args && Object.keys(args).length > 0 && (
            <div className="text-xs text-muted-foreground">
              {Object.entries(args).map(([key, value]) => (
                <div key={key}>
                  <span className="font-medium">{key}:</span> {String(value)}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="flex gap-3 justify-end">
          <Button variant="outline" onClick={() => cancelAction(messageId)}>
            <X className="h-4 w-4 mr-1" />
            取消
          </Button>
          <Button onClick={() => confirmAction(messageId)} className="bg-lego-green hover:bg-lego-green/90">
            <Check className="h-4 w-4 mr-1" />
            确认执行
          </Button>
        </div>
      </div>
    </div>
  )
}

export default ConfirmDialog
