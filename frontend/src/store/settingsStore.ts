/** 设置 Store */

import { create } from "zustand"
import type { Theme } from "../types"

interface SettingsState {
  theme: Theme
  apiBase: string
  model: string
  temperature: number
  toggleTheme: () => void
  updateSettings: (s: Partial<Omit<SettingsState, "toggleTheme" | "updateSettings">>) => void
}

export const useSettingsStore = create<SettingsState>((set) => ({
  theme: (localStorage.getItem("lego-theme") as Theme) || "light",
  apiBase: localStorage.getItem("lego-api-base") || "http://127.0.0.1:8000",
  model: localStorage.getItem("lego-model") || "LongCat-Flash-Chat",
  temperature: parseFloat(localStorage.getItem("lego-temperature") || "0.7"),

  toggleTheme: () =>
    set((state) => {
      const newTheme: Theme = state.theme === "light" ? "dark" : "light"
      localStorage.setItem("lego-theme", newTheme)
      document.documentElement.classList.toggle("dark", newTheme === "dark")
      return { theme: newTheme }
    }),

  updateSettings: (s) =>
    set((state) => {
      if (s.apiBase) localStorage.setItem("lego-api-base", s.apiBase)
      if (s.model) localStorage.setItem("lego-model", s.model)
      if (s.temperature !== undefined)
        localStorage.setItem("lego-temperature", String(s.temperature))
      if (s.theme) {
        localStorage.setItem("lego-theme", s.theme)
        document.documentElement.classList.toggle("dark", s.theme === "dark")
      }
      return { ...state, ...s }
    }),
}))
