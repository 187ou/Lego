/** 3D 拼装主页面 */

import { useEffect } from "react"
import { BuildScene } from "./BuildScene"
import { StepControls } from "./StepControls"
import { BrickInfoPanel } from "./BrickInfoPanel"
import { StepSidebar } from "./StepSidebar"
import { CelebrationOverlay } from "./CelebrationOverlay"
import { useBuilder3dStore, AVAILABLE_MODELS } from "@/store/builder3dStore"
import { useChatStore } from "@/store/chatStore"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Volume2, VolumeX, ChevronLeft, ChevronRight, Loader2 } from "lucide-react"
import { useState } from "react"
import { useChatStepSync } from "@/hooks/useChatStepSync"

export function Builder3D() {
  const {
    model,
    currentStep,
    isPlaying,
    soundEnabled,
    isLoading,
    useRealData,
    nextStep,
    setModel,
    toggleSound,
    loadFromAPI,
  } = useBuilder3dStore()
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const currentSet = useChatStore((s) => s.currentSet)

  // 启用聊天步骤联动
  useChatStepSync()

  // 自动播放
  useEffect(() => {
    if (!isPlaying) return
    const timer = setInterval(() => {
      nextStep()
    }, 2000)
    return () => clearInterval(timer)
  }, [isPlaying, nextStep])

  // 当聊天中的套装变化时，自动加载对应的拼装模型
  useEffect(() => {
    if (currentSet && !useRealData) {
      loadFromAPI(currentSet.set_id, currentSet.name, currentSet.total_steps)
    }
  }, [currentSet, useRealData, loadFromAPI])

  const currentStepData = model.steps[currentStep - 1]

  // 计算进度百分比
  const progress = Math.round((currentStep / model.totalSteps) * 100)

  return (
    <div className="relative w-full h-[calc(100vh-4rem)] overflow-hidden">
      {/* 加载遮罩 */}
      {isLoading && (
        <div className="absolute inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <p className="text-sm text-muted-foreground">加载拼装模型中...</p>
          </div>
        </div>
      )}

      {/* 3D 场景 */}
      <BuildScene />

      {/* 步骤描述（顶部） */}
      <div className="absolute top-4 left-1/2 -translate-x-1/2 px-6 py-3 bg-background/90 backdrop-blur-md rounded-lg border shadow-lg max-w-lg text-center">
        <p className="text-xs text-muted-foreground mb-1">
          步骤 {currentStep} / {model.totalSteps} · 进度 {progress}%
          {useRealData && " · 真实数据"}
        </p>
        <p className="font-medium text-sm">{currentStepData.description}</p>
      </div>

      {/* 步骤控制面板（底部悬浮） */}
      <div className="absolute bottom-4 left-1/2 -translate-x-1/2 w-80">
        <StepControls />
      </div>

      {/* 选中积木信息（右侧） */}
      <BrickInfoPanel />

      {/* 步骤侧边栏（左侧） */}
      <div className="absolute left-0 top-1/2 -translate-y-1/2 transition-transform duration-300">
        <div className="relative">
          {/* 切换按钮 */}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="absolute -right-6 top-1/2 -translate-y-1/2 z-10 w-6 h-12 bg-background/90 backdrop-blur border rounded-r-md flex items-center justify-center hover:bg-muted"
          >
            {sidebarOpen ? (
              <ChevronLeft className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
          </button>

          {/* 侧边栏内容 */}
          <div
            className={`transition-all duration-300 ${
              sidebarOpen ? "translate-x-4" : "-translate-x-full"
            }`}
          >
            <StepSidebar />
          </div>
        </div>
      </div>

      {/* 套装信息（左上角，在侧边栏关闭时显示） */}
      {!sidebarOpen && (
        <div className="absolute top-4 left-4 px-4 py-3 bg-background/90 backdrop-blur-md rounded-lg border shadow-lg">
          {/* 模型选择 */}
          <div className="mb-2">
            <Select
              value={model.setId}
              onValueChange={(value) => {
                const selected = AVAILABLE_MODELS.find((m) => m.setId === value)
                if (selected) setModel(selected)
              }}
            >
              <SelectTrigger className="w-40 h-8 text-sm">
                <SelectValue placeholder="选择模型" />
              </SelectTrigger>
              <SelectContent>
                {AVAILABLE_MODELS.map((m) => (
                  <SelectItem key={m.setId} value={m.setId}>
                    {m.setName}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <p className="text-xs text-muted-foreground">
            {model.totalBricks} 块 · {model.totalSteps} 步
          </p>
          {/* 进度条 */}
          <div className="mt-2 w-full bg-muted rounded-full h-1.5">
            <div
              className="bg-primary h-1.5 rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* 音效开关（右上角，在积木信息下方） */}
      <div className="absolute top-4 right-4 mt-24">
        <Button size="icon" variant="outline" onClick={toggleSound}>
          {soundEnabled ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
        </Button>
      </div>

      {/* 快捷键提示（右下角） */}
      <div className="absolute bottom-4 right-4 px-3 py-2 bg-background/80 backdrop-blur rounded-lg border text-xs text-muted-foreground">
        <p>🖱️ 左键旋转 · 右键平移 · 滚轮缩放</p>
      </div>

      {/* 完成庆祝动画 */}
      <CelebrationOverlay />
    </div>
  )
}
