/** 3D 积木组件 - 带凸点效果、高亮脉冲、音效触发 */

import { useRef, useState, useMemo, useEffect } from "react"
import { useFrame } from "@react-three/fiber"
import { Edges } from "@react-three/drei"
import * as THREE from "three"
import type { Brick } from "@/types/builder3d"
import { useBuilder3dStore } from "@/store/builder3dStore"

// 1 凸点 = 0.8 标准比例
const UNIT = 0.8
// 凸点半径
const STUD_RADIUS = 0.25
// 凸点高度
const STUD_HEIGHT = 0.18

interface Brick3DProps {
  brick: Brick
  isNew?: boolean // 是否是本步骤新添加（触发动画）
  isHighlighted?: boolean // 是否高亮
  explodeOffset?: number // 爆炸视图偏移量
  onClick?: (brick: Brick) => void
}

export function Brick3D({
  brick,
  isNew = false,
  isHighlighted = false,
  explodeOffset = 0,
  onClick,
}: Brick3DProps) {
  const meshRef = useRef<THREE.Group>(null)
  const [hovered, setHovered] = useState(false)
  const [animProgress, setAnimProgress] = useState(isNew ? 0 : 1)
  const prevIsNew = useRef(isNew)
  const pulseRef = useRef(0)
  const soundPlayed = useRef(false)

  // 积木实际尺寸
  const width = brick.size.x * UNIT
  const height = brick.size.y * UNIT
  const depth = brick.size.z * UNIT

  // 目标位置（含爆炸偏移）
  const targetX = brick.position.x * UNIT + width / 2
  const targetY = brick.position.y * UNIT + height / 2
  const targetZ = brick.position.z * UNIT + depth / 2

  // 爆炸视图偏移
  const explodeX = targetX + (targetX - 2) * explodeOffset * 0.3
  const explodeY = targetY + targetY * explodeOffset * 0.5
  const explodeZ = targetZ + (targetZ - 1.6) * explodeOffset * 0.3

  // 起始 Y 坐标（从上方落下）
  const startY = explodeY + 6

  // 生成凸点位置
  const studPositions = useMemo(() => {
    const positions: [number, number, number][] = []
    for (let x = 0; x < brick.size.x; x++) {
      for (let z = 0; z < brick.size.z; z++) {
        positions.push([
          (x - (brick.size.x - 1) / 2) * UNIT,
          height / 2 + STUD_HEIGHT / 2,
          (z - (brick.size.z - 1) / 2) * UNIT,
        ])
      }
    }
    return positions
  }, [brick.size, height])

  // 播放音效
  const playSound = () => {
    if (soundPlayed.current) return
    soundPlayed.current = true

    // 使用 Web Audio API 生成积木拼入声
    try {
      const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)()
      const oscillator = audioCtx.createOscillator()
      const gainNode = audioCtx.createGain()

      oscillator.connect(gainNode)
      gainNode.connect(audioCtx.destination)

      oscillator.frequency.setValueAtTime(800, audioCtx.currentTime)
      oscillator.frequency.exponentialRampToValueAtTime(200, audioCtx.currentTime + 0.1)

      gainNode.gain.setValueAtTime(0.3, audioCtx.currentTime)
      gainNode.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.15)

      oscillator.start(audioCtx.currentTime)
      oscillator.stop(audioCtx.currentTime + 0.15)
    } catch (e) {
      // 音效失败不影响主功能
    }
  }

  // 检测 isNew 变化
  useEffect(() => {
    if (isNew && !prevIsNew.current) {
      setAnimProgress(0)
      soundPlayed.current = false
    }
    prevIsNew.current = isNew
  }, [isNew])

  // 动画：新积木从上方落下
  useFrame((state, delta) => {
    if (!meshRef.current) return

    if (animProgress < 1) {
      const newProgress = Math.min(1, animProgress + delta * 3)
      setAnimProgress(newProgress)
      const t = easeOutBounce(newProgress)

      meshRef.current.position.y = THREE.MathUtils.lerp(startY, explodeY, t)

      // 落地时播放音效
      if (newProgress >= 1 && !soundPlayed.current) {
        playSound()
      }
    }

    // 高亮脉冲动画
    if (isHighlighted && animProgress >= 1) {
      pulseRef.current += delta * 4
      const pulse = Math.sin(pulseRef.current) * 0.5 + 0.5
      const floatY = Math.sin(state.clock.elapsedTime * 3) * 0.08
      meshRef.current.position.y = explodeY + floatY + pulse * 0.1
    }
  })

  return (
    <group
      ref={meshRef}
      position={[explodeX, isNew && animProgress < 1 ? startY : explodeY, explodeZ]}
      onClick={(e) => {
        e.stopPropagation()
        onClick?.(brick)
      }}
      onPointerOver={(e) => {
        e.stopPropagation()
        setHovered(true)
        document.body.style.cursor = "pointer"
      }}
      onPointerOut={() => {
        setHovered(false)
        document.body.style.cursor = "auto"
      }}
    >
      {/* 主体 */}
      <mesh castShadow receiveShadow>
        <boxGeometry args={[width, height, depth]} />
        <meshStandardMaterial
          color={brick.color}
          emissive={isHighlighted || hovered ? brick.color : "#000000"}
          emissiveIntensity={isHighlighted ? 0.5 : hovered ? 0.2 : 0}
          roughness={0.35}
          metalness={0.05}
        />
        <Edges color="#00000020" threshold={15} />
      </mesh>

      {/* 顶部凸点 */}
      {studPositions.map((pos, i) => (
        <mesh key={i} position={pos} castShadow>
          <cylinderGeometry args={[STUD_RADIUS, STUD_RADIUS, STUD_HEIGHT, 16]} />
          <meshStandardMaterial
            color={brick.color}
            roughness={0.3}
            metalness={0.05}
            emissive={isHighlighted || hovered ? brick.color : "#000000"}
            emissiveIntensity={isHighlighted ? 0.3 : hovered ? 0.15 : 0}
          />
        </mesh>
      ))}

      {/* 高亮光环 */}
      {isHighlighted && (
        <mesh position={[0, -height / 2 + 0.05, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[Math.max(width, depth) * 0.6, Math.max(width, depth) * 0.8, 32]} />
          <meshBasicMaterial color={brick.color} transparent opacity={0.4} />
        </mesh>
      )}
    </group>
  )
}

// 缓动函数：弹跳效果
function easeOutBounce(t: number): number {
  const n1 = 7.5625
  const d1 = 2.75
  if (t < 1 / d1) {
    return n1 * t * t
  } else if (t < 2 / d1) {
    return n1 * (t -= 1.5 / d1) * t + 0.75
  } else if (t < 2.5 / d1) {
    return n1 * (t -= 2.25 / d1) * t + 0.9375
  } else {
    return n1 * (t -= 2.625 / d1) * t + 0.984375
  }
}
