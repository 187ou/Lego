/** 欢迎屏幕 - 无消息时展示 */

import { useChatStore } from "../../store/chatStore"
import { Button } from "../ui/button"
import { Camera, Search, BookOpen, CheckCircle } from "lucide-react"

const WelcomeScreen: React.FC = () => {
  const sendMessage = useChatStore((s) => s.sendMessage)

  const suggestions = [
    {
      icon: Camera,
      label: "识别零件",
      message: "请帮我识别这个零件是什么",
      color: "text-lego-red",
    },
    {
      icon: Search,
      label: "查找替代",
      message: "红色 2x4 砖有什么替代方案？",
      color: "text-lego-blue",
    },
    {
      icon: BookOpen,
      label: "说明书步骤",
      message: "第 35 步怎么拼？",
      color: "text-lego-green",
    },
    {
      icon: CheckCircle,
      label: "成品验收",
      message: "帮我看下这一步拼得对么",
      color: "text-lego-orange",
    },
  ]

  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="text-center max-w-md">
        <div className="text-6xl mb-4">🧱</div>
        <h2 className="text-2xl font-bold mb-2">你好！我是 LEGO-Mate</h2>
        <p className="text-muted-foreground mb-8">
          你的智能拼搭助手，可以帮你识别零件、查找替代、检索说明书、验收成品
        </p>

        <div className="grid grid-cols-2 gap-3">
          {suggestions.map((s) => (
            <Button
              key={s.label}
              variant="outline"
              className="h-auto py-4 flex flex-col items-center gap-2 hover:bg-muted"
              onClick={() => sendMessage(s.message)}
            >
              <s.icon className={`h-6 w-6 ${s.color}`} />
              <span className="text-sm">{s.label}</span>
            </Button>
          ))}
        </div>
      </div>
    </div>
  )
}

export default WelcomeScreen
