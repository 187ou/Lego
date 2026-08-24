/** UI 状态 Store */

import { create } from "zustand"

interface UIState {
  sidebarOpen: boolean
  settingsOpen: boolean
  historyOpen: boolean
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
  setSettingsOpen: (open: boolean) => void
  setHistoryOpen: (open: boolean) => void
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: true,
  settingsOpen: false,
  historyOpen: false,

  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  setSettingsOpen: (open) => set({ settingsOpen: open }),
  setHistoryOpen: (open) => set({ historyOpen: open }),
}))
