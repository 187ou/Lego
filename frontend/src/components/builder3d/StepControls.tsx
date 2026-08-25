/** 步骤控制面板 */

import { Button } from "@/components/ui/button"
import { Slider } from "@/components/ui/slider"
import { Play, Pause, SkipBack, SkipForward, RotateCcw, Expand, Shrink } from "lucide-react"
import { useBuilder3dStore } from "@/store/builder3dStore"

export function StepControls() {
  const {
    currentStep,
    totalSteps,
    isPlaying,
    explodeMode,
    nextStep,
    prevStep,
    goToStep,
    togglePlay,
    toggleExplode,
    reset,
  } = useBuilder3dStore()

  return (
    <div className="flex flex-col gap-3 p-4 bg-background/90 backdrop-blur-md rounded-lg border shadow-lg">
      {/* 步骤信息 */}
      <div className="text-center">
        <span className="text-2xl font-bold">{currentStep}</span>
        <span className="text-muted-foreground"> / {totalSteps}</span>
      </div>

      {/* 进度条 */}
      <Slider
        value={[currentStep]}
        min={1}
        max={totalSteps}
        step={1}
        onValueChange={([val]) => goToStep(val)}
        className="w-full"
      />

      {/* 控制按钮 */}
      <div className="flex justify-center gap-2">
        <Button size="icon" variant="outline" onClick={() => goToStep(1)}>
          <SkipBack className="h-4 w-4" />
        </Button>
        <Button size="icon" variant="outline" onClick={prevStep} disabled={currentStep <= 1}>
          <RotateCcw className="h-4 w-4" />
        </Button>
        <Button size="icon" onClick={togglePlay}>
          {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
        </Button>
        <Button
          size="icon"
          variant="outline"
          onClick={nextStep}
          disabled={currentStep >= totalSteps}
        >
          <SkipForward className="h-4 w-4" />
        </Button>
        <Button size="icon" variant="outline" onClick={reset}>
          <RotateCcw className="h-4 w-4" />
        </Button>
      </div>

      {/* 爆炸视图按钮 */}
      <div className="flex justify-center">
        <Button
          size="sm"
          variant={explodeMode ? "default" : "outline"}
          onClick={toggleExplode}
          className="gap-2"
        >
          {explodeMode ? <Shrink className="h-4 w-4" /> : <Expand className="h-4 w-4" />}
          {explodeMode ? "合并视图" : "爆炸视图"}
        </Button>
      </div>
    </div>
  )
}
