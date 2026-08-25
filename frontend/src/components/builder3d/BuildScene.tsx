/** 3D 拼装场景 - 含相机跟随、爆炸视图、步骤动画 */

import { useRef, useEffect, useState } from "react"
import { Canvas, useThree, useFrame } from "@react-three/fiber"
import { OrbitControls, Environment, ContactShadows, Grid, PerspectiveCamera } from "@react-three/drei"
import { Brick3D } from "./Brick3D"
import { useBuilder3dStore } from "@/store/builder3dStore"
import type { Brick } from "@/types/builder3d"
import * as THREE from "three"

/** 相机位置状态 */
interface CameraState {
  position: THREE.Vector3
  target: THREE.Vector3
}

/** 相机跟随组件 - 带平滑动画 */
function CameraFollow({
  targetPosition,
  stepChanged,
}: {
  targetPosition: THREE.Vector3
  stepChanged: boolean
}) {
  const { camera } = useThree()
  const controlsRef = useRef<any>(null)
  const [cameraState, setCameraState] = useState<CameraState>({
    position: new THREE.Vector3(12, 10, 12),
    target: new THREE.Vector3(2, 2, 3),
  })
  const animationProgress = useRef(1)

  // 步骤变化时触发动画
  useEffect(() => {
    if (stepChanged) {
      animationProgress.current = 0
      const startPosition = camera.position.clone()
      const startTarget = controlsRef.current?.target?.clone() || new THREE.Vector3()

      // 计算新的相机位置（基于目标点偏移）
      const offset = new THREE.Vector3(8, 6, 8)
      const newPosition = targetPosition.clone().add(offset)

      setCameraState({
        position: newPosition,
        target: targetPosition.clone(),
      })

      // 保存起始位置用于插值
      startPos.current = startPosition
      startTargetRef.current = startTarget
    }
  }, [stepChanged, targetPosition, camera])

  const startPos = useRef(new THREE.Vector3(12, 10, 12))
  const startTargetRef = useRef(new THREE.Vector3(2, 2, 3))

  useFrame((_, delta) => {
    if (animationProgress.current < 1) {
      animationProgress.current = Math.min(1, animationProgress.current + delta * 1.5)
      const t = easeInOutCubic(animationProgress.current)

      // 插值相机位置
      if (controlsRef.current) {
        camera.position.lerpVectors(startPos.current, cameraState.position, t)
        controlsRef.current.target.lerpVectors(startTargetRef.current, cameraState.target, t)
        controlsRef.current.update()
      }
    } else {
      // 平时缓慢跟随
      if (controlsRef.current) {
        controlsRef.current.target.lerp(targetPosition, 0.03)
        controlsRef.current.update()
      }
    }
  })

  return (
    <OrbitControls
      ref={controlsRef}
      enablePan={true}
      enableZoom={true}
      enableRotate={true}
      minDistance={5}
      maxDistance={50}
      maxPolarAngle={Math.PI / 2 - 0.1}
    />
  )
}

/** 缓动函数 */
function easeInOutCubic(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2
}

/** 场景内容 */
function SceneContent() {
  const { model, currentStep, selectBrick, explodeMode } = useBuilder3dStore()
  const [stepChanged, setStepChanged] = useState(false)

  // 获取当前步骤为止所有应显示的积木
  const visibleBricks = model.steps.slice(0, currentStep).flatMap((step) => step.bricksToAdd)

  // 当前步骤新添加的积木 ID
  const newBrickIds = new Set(model.steps[currentStep - 1]?.bricksToAdd.map((b) => b.id) || [])

  // 当前步骤高亮的积木 ID
  const highlightIds = new Set(model.steps[currentStep - 1]?.bricksHighlight || [])

  // 计算当前步骤的中心点（用于相机跟随）
  const currentBricks = model.steps[currentStep - 1]?.bricksToAdd || []
  const centerPosition = useRef(new THREE.Vector3(2, 2, 3))

  useEffect(() => {
    setStepChanged(true)
    const timer = setTimeout(() => setStepChanged(false), 100)

    if (currentBricks.length > 0) {
      let avgX = 0,
        avgY = 0,
        avgZ = 0
      currentBricks.forEach((b) => {
        avgX += b.position.x * 0.8 + (b.size.x * 0.8) / 2
        avgY += b.position.y * 0.8 + (b.size.y * 0.8) / 2
        avgZ += b.position.z * 0.8 + (b.size.z * 0.8) / 2
      })
      centerPosition.current.set(
        avgX / currentBricks.length,
        avgY / currentBricks.length,
        avgZ / currentBricks.length
      )
    }

    return () => clearTimeout(timer)
  }, [currentStep, currentBricks])

  const handleBrickClick = (brick: Brick) => {
    selectBrick(brick)
  }

  return (
    <>
      {/* 灯光 */}
      <ambientLight intensity={0.6} />
      <directionalLight
        position={[10, 20, 10]}
        intensity={1.2}
        castShadow
        shadow-mapSize={[2048, 2048]}
      />
      <pointLight position={[-10, 10, -10]} intensity={0.5} />

      {/* 环境反射 */}
      <Environment preset="city" />

      {/* 积木渲染 */}
      {visibleBricks.map((brick) => (
        <Brick3D
          key={brick.id}
          brick={brick}
          isNew={newBrickIds.has(brick.id)}
          isHighlighted={highlightIds.has(brick.id)}
          explodeOffset={explodeMode ? 1 : 0}
          onClick={handleBrickClick}
        />
      ))}

      {/* 网格底面 */}
      <Grid
        position={[0, -0.01, 0]}
        args={[20, 20]}
        cellSize={0.8}
        cellThickness={0.5}
        cellColor="#4a4a6a"
        sectionSize={4}
        sectionThickness={1}
        sectionColor="#6a6a8a"
        fadeDistance={30}
        infiniteGrid
      />

      {/* 阴影 */}
      <ContactShadows position={[0, -0.01, 0]} opacity={0.4} scale={20} blur={2} />

      {/* 相机跟随 */}
      <CameraFollow targetPosition={centerPosition.current} stepChanged={stepChanged} />
    </>
  )
}

export function BuildScene() {
  return (
    <Canvas
      shadows
      style={{ background: "linear-gradient(180deg, #1a1a2e 0%, #16213e 100%)" }}
    >
      <PerspectiveCamera makeDefault position={[12, 10, 12]} fov={50} />
      <SceneContent />
    </Canvas>
  )
}
