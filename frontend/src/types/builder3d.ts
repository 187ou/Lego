/** 3D 拼装类型定义 */

/** 单个积木 */
export interface Brick {
  id: string
  partId: string // 零件编号，如 "3001"
  name: string // 如 "Brick 2x4"
  color: string // 十六进制颜色，如 "#E3000B"
  colorName: string // 如 "Red"
  size: { x: number; y: number; z: number } // 以"凸点"为单位
  position: { x: number; y: number; z: number } // 世界坐标（凸点单位）
  rotation?: { x: number; y: number; z: number } // 旋转（弧度）
}

/** 单个步骤 */
export interface BuildStep {
  stepNumber: number
  description: string // 步骤描述
  bricksToAdd: Brick[] // 本步骤新增的积木
  bricksHighlight?: string[] // 需要高亮的积木 ID
  cameraPosition?: [number, number, number] // 推荐相机位置
}

/** 完整模型 */
export interface BuildModel {
  setId: string
  setName: string
  totalSteps: number
  totalBricks: number
  steps: BuildStep[]
  basePlate: { width: number; length: number } // 底板尺寸（凸点单位）
}

/** 后端 API 返回的积木数据格式 */
export interface BrickAPI {
  id: string
  partId: string
  name: string
  color: string
  colorName: string
  size: { x: number; y: number; z: number }
  position: { x: number; y: number; z: number }
}

/** 后端 API 返回的步骤数据格式 */
export interface BuildStepAPI {
  stepNumber: number
  description: string
  bricksToAdd: BrickAPI[]
  bricksHighlight?: string[]
}

/** 后端 API 返回的模型数据格式 */
export interface BuildModelAPI {
  setId: string
  setName: string
  totalSteps: number
  totalBricks: number
  steps: BuildStepAPI[]
  basePlate: { width: number; length: number }
}

/** 将后端 API 数据转换为前端模型 */
export function convertAPIToModel(api: BuildModelAPI): BuildModel {
  return {
    setId: api.setId,
    setName: api.setName,
    totalSteps: api.totalSteps,
    totalBricks: api.totalBricks,
    basePlate: api.basePlate,
    steps: api.steps.map((step) => ({
      stepNumber: step.stepNumber,
      description: step.description,
      bricksHighlight: step.bricksHighlight,
      bricksToAdd: step.bricksToAdd.map((brick) => ({
        id: brick.id,
        partId: brick.partId,
        name: brick.name,
        color: brick.color,
        colorName: brick.colorName,
        size: brick.size,
        position: brick.position,
      })),
    })),
  }
}
