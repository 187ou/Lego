/** 单条对话项 */

import { cn } from "../../lib/utils"
import { MessageSquare, Trash2 } from "lucide-react"
import type { ConversationMeta } from "../../types"

interface ConversationItemProps {
  conversation: ConversationMeta
  isActive: boolean
  onSelect: () => void
  onDelete: () => void
}

const ConversationItem: React.FC<ConversationItemProps> = ({
  conversation,
  isActive,
  onSelect,
  onDelete,
}) => {
  return (
    <div
      onClick={onSelect}
      className={cn(
        "group flex items-center gap-2 px-3 py-2.5 rounded-lg cursor-pointer transition-all",
        isActive
          ? "bg-primary text-primary-foreground"
          : "hover:bg-muted text-foreground"
      )}
    >
      <MessageSquare className="h-4 w-4 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium truncate">{conversation.title}</div>
        <div
          className={cn(
            "text-xs truncate",
            isActive ? "text-primary-foreground/70" : "text-muted-foreground"
          )}
        >
          {new Date(conversation.updated_at).toLocaleDateString()}
        </div>
      </div>
      <button
        onClick={(e) => {
          e.stopPropagation()
          onDelete()
        }}
        className={cn(
          "p-1 rounded opacity-0 group-hover:opacity-100 transition",
          isActive
            ? "hover:bg-primary-foreground/20"
            : "hover:bg-muted-foreground/20"
        )}
      >
        <Trash2 className="h-3.5 w-3.5" />
      </button>
    </div>
  )
}

export default ConversationItem
