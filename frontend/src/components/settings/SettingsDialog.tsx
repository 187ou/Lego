/** 设置面板 */

import { useState } from "react"
import { Dialog, DialogTitle } from "../ui/dialog"
import { Button } from "../ui/button"
import { Input } from "../ui/input"
import { Label } from "../ui/label"
import { Switch } from "../ui/switch"
import { Select } from "../ui/select"
import { useUIStore } from "../../store/uiStore"
import { useSettingsStore } from "../../store/settingsStore"
import { useChatStore } from "../../store/chatStore"
import { Sun, Moon, Trash2, Download } from "lucide-react"
import { Tabs } from "../ui/tabs"

const SettingsDialog: React.FC = () => {
  const { settingsOpen, setSettingsOpen } = useUIStore()
  const { theme, apiBase, model, temperature, toggleTheme, updateSettings } =
    useSettingsStore()
  const [activeTab, setActiveTab] = useState("general")
  const messages = useChatStore((s) => s.messages)

  const handleExportMarkdown = () => {
    const md = messages
      .map((m) => {
        const role = m.role === "user" ? "**👤 你**" : "**🤖 LEGO-Mate**"
        return `${role}\n\n${m.content}\n`
      })
      .join("\n---\n\n")

    const blob = new Blob([md], { type: "text/markdown" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `lego-mate-${new Date().toISOString().slice(0, 10)}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleClearData = () => {
    if (confirm("确定要清除所有对话数据吗？此操作不可恢复。")) {
      localStorage.clear()
      window.location.reload()
    }
  }

  const tabs = [
    { id: "general", label: "通用" },
    { id: "api", label: "API" },
    { id: "data", label: "数据" },
  ]

  return (
    <Dialog open={settingsOpen} onClose={() => setSettingsOpen(false)}>
      <DialogTitle>设置</DialogTitle>

      <Tabs tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab} className="mb-4" />

      {activeTab === "general" && (
        <div className="space-y-4">
          {/* 主题切换 */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {theme === "dark" ? (
                <Moon className="h-4 w-4" />
              ) : (
                <Sun className="h-4 w-4" />
              )}
              <Label>暗色模式</Label>
            </div>
            <Switch checked={theme === "dark"} onCheckedChange={toggleTheme} />
          </div>

          {/* 模型温度 */}
          <div className="space-y-2">
            <Label>回复创意度 (Temperature)</Label>
            <div className="flex items-center gap-3">
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={temperature}
                onChange={(e) => updateSettings({ temperature: parseFloat(e.target.value) })}
                className="flex-1"
              />
              <span className="text-sm text-muted-foreground w-8">{temperature}</span>
            </div>
          </div>
        </div>
      )}

      {activeTab === "api" && (
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>API Base URL</Label>
            <Input
              value={apiBase}
              onChange={(e) => updateSettings({ apiBase: e.target.value })}
              placeholder="http://127.0.0.1:8000"
            />
          </div>
          <div className="space-y-2">
            <Label>模型</Label>
            <Select
              value={model}
              onValueChange={(v) => updateSettings({ model: v })}
              options={[
                { value: "LongCat-Flash-Chat", label: "LongCat-Flash-Chat" },
                { value: "gpt-4o", label: "GPT-4o" },
                { value: "gpt-4o-mini", label: "GPT-4o-mini" },
                { value: "qwen-vl-plus", label: "Qwen-VL-Plus" },
              ]}
            />
          </div>
        </div>
      )}

      {activeTab === "data" && (
        <div className="space-y-4">
          <Button variant="outline" className="w-full" onClick={handleExportMarkdown}>
            <Download className="h-4 w-4 mr-2" />
            导出对话为 Markdown
          </Button>
          <Button variant="destructive" className="w-full" onClick={handleClearData}>
            <Trash2 className="h-4 w-4 mr-2" />
            清除所有数据
          </Button>
        </div>
      )}
    </Dialog>
  )
}

export default SettingsDialog
