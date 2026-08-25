/** 聊天与3D拼装联动 Hook
 *
 * 监听聊天消息中的步骤号引用，自动跳转到对应步骤
 * 支持格式：第35步、step 35、35步
 *
 * 使用方式：在 Builder3D 组件中调用此 hook
 */

import { useEffect, useRef } from "react"
import { useBuilder3dStore } from "@/store/builder3dStore"
import { useChatStore } from "@/store/chatStore"

export function useChatStepSync() {
  const { model, goToStep } = useBuilder3dStore()
  const messages = useChatStore((s) => s.messages)
  const lastProcessedId = useRef<string | null>(null)

  useEffect(() => {
    if (messages.length === 0) return

    // 只处理最新消息
    const latestMsg = messages[messages.length - 1]
    if (latestMsg.id === lastProcessedId.current) return
    lastProcessedId.current = latestMsg.id

    // 只处理 AI 消息
    if (latestMsg.role !== "assistant") return

    // 从消息内容中提取步骤号
    const content = latestMsg.content

    // 匹配模式：第35步、第 35 步、step 35、35步
    const patterns = [
      /第\s*(\d+)\s*步/gi,
      /step\s*(\d+)/gi,
      /(\d+)\s*步/gi,
    ]

    for (const pattern of patterns) {
      const matches = content.match(pattern)
      if (matches) {
        // 取第一个匹配的步骤号
        const stepStr = matches[0].replace(/\D/g, "")
        const stepNum = parseInt(stepStr, 10)

        // 检查步骤号是否在有效范围内
        if (stepNum >= 1 && stepNum <= model.totalSteps) {
          goToStep(stepNum)
          break
        }
      }
    }
  }, [messages, model.totalSteps, goToStep])
}
