/** 侧边栏 */

import { Button } from "../ui/button"
import { Separator } from "../ui/separator"
import { Plus, PanelLeftClose } from "lucide-react"
import ConversationList from "./ConversationList"
import SetSelector from "./SetSelector"
import ProgressTracker from "../progress/ProgressTracker"
import FrustrationIndicator from "../progress/FrustrationIndicator"
import { useChatStore } from "../../store/chatStore"
import { useUIStore } from "../../store/uiStore"

const Sidebar: React.FC = () => {
  const createNewConversation = useChatStore((s) => s.createNewConversation)
  const sidebarOpen = useUIStore((s) => s.sidebarOpen)
  const setSidebarOpen = useUIStore((s) => s.setSidebarOpen)

  if (!sidebarOpen) return null

  return (
    <aside className="w-72 border-r bg-card flex flex-col h-full">
      {/* 顶部 */}
      <div className="p-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xl">🧱</span>
          <span className="font-bold">LEGO-Mate</span>
        </div>
        <Button variant="ghost" size="icon" onClick={() => setSidebarOpen(false)}>
          <PanelLeftClose className="h-4 w-4" />
        </Button>
      </div>

      {/* 新建对话 */}
      <div className="px-3 pb-2">
        <Button
          onClick={() => createNewConversation()}
          className="w-full bg-lego-red hover:bg-lego-red/90"
        >
          <Plus className="h-4 w-4 mr-2" />
          新建对话
        </Button>
      </div>

      <Separator />

      {/* 套装选择器 */}
      <SetSelector />

      <Separator />

      {/* 对话列表 */}
      <div className="flex-1 overflow-hidden">
        <div className="px-3 py-2">
          <span className="text-xs font-medium text-muted-foreground">对话历史</span>
        </div>
        <ConversationList />
      </div>

      <Separator />

      {/* 进度和情绪 */}
      <div className="p-3 space-y-3">
        <ProgressTracker />
        <FrustrationIndicator />
      </div>
    </aside>
  )
}

export default Sidebar
