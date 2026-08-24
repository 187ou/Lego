/** 套装选择器 */

import { useEffect } from "react"
import { useChatStore } from "../../store/chatStore"
import { Select } from "../ui/select"
import { Blocks } from "lucide-react"

const SetSelector: React.FC = () => {
  const sets = useChatStore((s) => s.sets)
  const currentSet = useChatStore((s) => s.currentSet)
  const loadSets = useChatStore((s) => s.loadSets)
  const setCurrentSet = useChatStore((s) => s.setCurrentSet)

  useEffect(() => {
    loadSets()
  }, [loadSets])

  const options = sets.map((s) => ({
    value: s.set_id,
    label: `${s.set_id} ${s.name}`,
  }))

  return (
    <div className="px-3 py-2">
      <div className="flex items-center gap-2 mb-2">
        <Blocks className="h-4 w-4 text-muted-foreground" />
        <span className="text-xs font-medium text-muted-foreground">当前套装</span>
      </div>
      <Select
        value={currentSet?.set_id || ""}
        onValueChange={(v) => setCurrentSet(v)}
        options={options}
        placeholder="选择套装..."
      />
    </div>
  )
}

export default SetSelector
