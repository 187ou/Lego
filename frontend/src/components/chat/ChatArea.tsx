/** 聊天区域 - 右侧主区域 */

import { useChatStore } from "../../store/chatStore"
import MessageList from "./MessageList"
import MessageInput from "./MessageInput"
import WelcomeScreen from "./WelcomeScreen"
import { Button } from "../ui/button"
import { Settings, Plus, Menu, History } from "lucide-react"
import { useUIStore } from "../../store/uiStore"

const ChatArea: React.FC = () => {
  const messages = useChatStore((s) => s.messages)
  const currentSet = useChatStore((s) => s.currentSet)
  const createNewConversation = useChatStore((s) => s.createNewConversation)
  const toggleSidebar = useUIStore((s) => s.toggleSidebar)
  const setSettingsOpen = useUIStore((s) => s.setSettingsOpen)
  const setHistoryOpen = useUIStore((s) => s.setHistoryOpen)

  return (
    <div className="flex-1 flex flex-col min-w-0 bg-background">
      {/* 顶部栏 */}
      <header className="flex items-center justify-between px-4 py-3 border-b bg-card">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" className="lg:hidden" onClick={toggleSidebar}>
            <Menu className="h-5 w-5" />
          </Button>
          <div className="flex items-center gap-2">
            <span className="text-xl">🧱</span>
            <div>
              <h1 className="font-bold text-lg leading-tight">LEGO-Mate</h1>
              {currentSet && (
                <p className="text-xs text-muted-foreground">{currentSet.name}</p>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={() => createNewConversation()}>
            <Plus className="h-5 w-5" />
          </Button>
          <Button variant="ghost" size="icon" onClick={() => setHistoryOpen(true)} title="历史对话">
            <History className="h-5 w-5" />
          </Button>
          <Button variant="ghost" size="icon" onClick={() => setSettingsOpen(true)}>
            <Settings className="h-5 w-5" />
          </Button>
        </div>
      </header>

      {/* 消息区域或欢迎屏幕 */}
      {messages.length === 0 ? <WelcomeScreen /> : <MessageList />}

      {/* 输入区域 */}
      <MessageInput />
    </div>
  )
}

export default ChatArea
