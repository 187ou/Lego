/** 主应用组件 - 布局壳 */

import { useEffect } from "react"
import Sidebar from "./components/sidebar/Sidebar"
import ChatArea from "./components/chat/ChatArea"
import SettingsDialog from "./components/settings/SettingsDialog"
import ConfirmDialog from "./components/chat/ConfirmDialog"
import HistoryDialog from "./components/history/HistoryDialog"
import { useChatStore } from "./store/chatStore"
import { useSettingsStore } from "./store/settingsStore"
import { useUIStore } from "./store/uiStore"

const App: React.FC = () => {
  const loadConversations = useChatStore((s) => s.loadConversations)
  const createNewConversation = useChatStore((s) => s.createNewConversation)
  const currentConversationId = useChatStore((s) => s.currentConversationId)
  const theme = useSettingsStore((s) => s.theme)
  const historyOpen = useUIStore((s) => s.historyOpen)
  const setHistoryOpen = useUIStore((s) => s.setHistoryOpen)

  // 初始化
  useEffect(() => {
    // 应用主题
    document.documentElement.classList.toggle("dark", theme === "dark")

    // 加载对话列表
    loadConversations().then(() => {
      // 如果没有对话，创建一个
      if (!currentConversationId) {
        createNewConversation()
      }
    })
  }, [])

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      <Sidebar />
      <ChatArea />
      <SettingsDialog />
      <ConfirmDialog />
      <HistoryDialog open={historyOpen} onClose={() => setHistoryOpen(false)} />
    </div>
  )
}

export default App
