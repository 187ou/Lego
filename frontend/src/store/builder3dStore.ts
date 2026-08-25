/** 3D 拼装状态管理 */

import { create } from "zustand"
import type { Brick, BuildModel } from "@/types/builder3d"
import { convertAPIToModel } from "@/types/builder3d"
import { mockBuildModel } from "@/data/mockBuildModel"
import { mockCastleModel } from "@/data/mockCastleModel"
import { getBuildModel } from "@/lib/api"

// 可用模型列表
export const AVAILABLE_MODELS: BuildModel[] = [mockBuildModel, mockCastleModel]

interface Builder3dState {
  // 当前模型
  model: BuildModel
  // 当前步骤（1-based）
  currentStep: number
  // 是否自动播放
  isPlaying: boolean
  // 选中的积木
  selectedBrick: Brick | null
  // 爆炸视图模式
  explodeMode: boolean
  // 音效开关
  soundEnabled: boolean
  // 加载状态
  isLoading: boolean
  // 是否使用真实数据
  useRealData: boolean

  // Actions
  setModel: (model: BuildModel) => void
  setCurrentStep: (step: number) => void
  nextStep: () => void
  prevStep: () => void
  goToStep: (step: number) => void
  togglePlay: () => void
  setPlaying: (playing: boolean) => void
  selectBrick: (brick: Brick | null) => void
  toggleExplode: () => void
  setExplode: (explode: boolean) => void
  toggleSound: () => void
  reset: () => void
  loadFromAPI: (setId: string, setName?: string, totalSteps?: number) => Promise<void>
}

export const useBuilder3dStore = create<Builder3dState>((set, get) => ({
  model: mockBuildModel,
  currentStep: 1,
  isPlaying: false,
  selectedBrick: null,
  explodeMode: false,
  soundEnabled: true,
  isLoading: false,
  useRealData: false,

  setModel: (model) =>
    set({
      model,
      currentStep: 1,
      selectedBrick: null,
      explodeMode: false,
      isPlaying: false,
    }),

  setCurrentStep: (step) => {
    const { model } = get()
    const clamped = Math.max(1, Math.min(step, model.totalSteps))
    set({ currentStep: clamped })
  },

  nextStep: () => {
    const { currentStep, model } = get()
    if (currentStep < model.totalSteps) {
      set({ currentStep: currentStep + 1 })
    } else {
      set({ isPlaying: false })
    }
  },

  prevStep: () => {
    const { currentStep } = get()
    if (currentStep > 1) {
      set({ currentStep: currentStep - 1 })
    }
  },

  goToStep: (step) => {
    const { model } = get()
    const clamped = Math.max(1, Math.min(step, model.totalSteps))
    set({ currentStep: clamped })
  },

  togglePlay: () => set((state) => ({ isPlaying: !state.isPlaying })),
  setPlaying: (playing) => set({ isPlaying: playing }),

  selectBrick: (brick) => set({ selectedBrick: brick }),

  toggleExplode: () => set((state) => ({ explodeMode: !state.explodeMode })),
  setExplode: (explode) => set({ explodeMode: explode }),

  toggleSound: () => set((state) => ({ soundEnabled: !state.soundEnabled })),

  reset: () =>
    set({
      currentStep: 1,
      isPlaying: false,
      selectedBrick: null,
      explodeMode: false,
    }),

  loadFromAPI: async (setId: string, setName?: string, totalSteps?: number) => {
    set({ isLoading: true })
    try {
      const apiData = await getBuildModel(setId, setName, totalSteps)
      const model = convertAPIToModel(apiData)
      set({
        model,
        currentStep: 1,
        selectedBrick: null,
        explodeMode: false,
        isPlaying: false,
        useRealData: true,
        isLoading: false,
      })
    } catch (error) {
      console.error("加载拼装模型失败:", error)
      set({ isLoading: false })
      // 失败时使用 mock 数据
      set({ model: mockBuildModel, useRealData: false })
    }
  },
}))
