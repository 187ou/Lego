/** 完成庆祝动画 */

import { useEffect, useState } from "react"
import { useBuilder3dStore } from "@/store/builder3dStore"
import { Button } from "@/components/ui/button"
import { PartyPopper, RotateCcw } from "lucide-react"

interface Particle {
  id: number
  x: number
  y: number
  color: string
  delay: number
}

export function CelebrationOverlay() {
  const { model, currentStep, reset } = useBuilder3dStore()
  const [show, setShow] = useState(false)
  const [particles, setParticles] = useState<Particle[]>([])

  const isComplete = currentStep === model.totalSteps

  useEffect(() => {
    if (isComplete) {
      // 生成庆祝粒子
      const colors = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7", "#DDA0DD", "#98D8C8"]
      const newParticles: Particle[] = []
      for (let i = 0; i < 50; i++) {
        newParticles.push({
          id: i,
          x: Math.random() * 100,
          y: Math.random() * 100,
          color: colors[Math.floor(Math.random() * colors.length)],
          delay: Math.random() * 0.5,
        })
      }
      setParticles(newParticles)
      setShow(true)
    } else {
      setShow(false)
    }
  }, [isComplete, model.totalSteps])

  if (!show) return null

  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm animate-in fade-in">
      {/* 粒子效果 */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        {particles.map((p) => (
          <div
            key={p.id}
            className="absolute w-3 h-3 rounded-full animate-bounce"
            style={{
              left: `${p.x}%`,
              top: `${p.y}%`,
              backgroundColor: p.color,
              animationDelay: `${p.delay}s`,
              animationDuration: "1s",
            }}
          />
        ))}
      </div>

      {/* 庆祝卡片 */}
      <div className="relative bg-background rounded-xl border shadow-2xl p-8 text-center max-w-sm mx-4 animate-in zoom-in">
        <div className="text-6xl mb-4">🎉</div>
        <h2 className="text-2xl font-bold mb-2">拼装完成！</h2>
        <p className="text-muted-foreground mb-6">
          恭喜你完成了 <strong>{model.setName}</strong> 的拼装！
          <br />
          共使用了 {model.totalBricks} 块积木，{model.totalSteps} 个步骤。
        </p>

        <div className="flex gap-3 justify-center">
          <Button onClick={reset} variant="outline">
            <RotateCcw className="h-4 w-4 mr-2" />
            重新拼装
          </Button>
          <Button onClick={() => setShow(false)}>
            <PartyPopper className="h-4 w-4 mr-2" />
            继续欣赏
          </Button>
        </div>
      </div>
    </div>
  )
}
