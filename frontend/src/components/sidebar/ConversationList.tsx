/** 对话列表 */

import { ScrollArea } from "../ui/scroll-area"
import ConversationItem from "./ConversationItem"
import { useChatStore } from "../../store/chatStore"

const ConversationList: React.FC = () => {
  const conversations = useChatStore((s) => s.conversations)
  const currentConversationId = useChatStore((s) => s.currentConversationId)
  const switchConversation = useChatStore((s) => s.switchConversation)
  const deleteConversation = useChatStore((s) => s.deleteConversation)

  if (conversations.length === 0) {
    return (
      <div className="p-4 text-center text-sm text-muted-foreground">
        暂无对话记录
      </div>
    )
  }

  return (
    <ScrollArea className="flex-1 px-2">
      <div className="space-y-1 py-2">
        {conversations.map((conv) => (
          <ConversationItem
            key={conv.id}
            conversation={conv}
            isActive={conv.id === currentConversationId}
            onSelect={() => switchConversation(conv.id)}
            onDelete={() => deleteConversation(conv.id)}
          />
        ))}
      </div>
    </ScrollArea>
  )
}

export default ConversationList
