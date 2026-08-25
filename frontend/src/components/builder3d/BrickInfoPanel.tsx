/** 积木信息面板 */

import { useBuilder3dStore } from "@/store/builder3dStore"

export function BrickInfoPanel() {
  const { selectedBrick, selectBrick } = useBuilder3dStore()

  if (!selectedBrick) return null

  return (
    <div className="absolute top-4 right-4 p-4 bg-background/90 backdrop-blur-md rounded-lg border shadow-lg w-56 animate-in fade-in slide-in-from-right-2">
      <div className="flex justify-between items-start mb-3">
        <h3 className="font-bold text-sm">{selectedBrick.name}</h3>
        <button
          onClick={() => selectBrick(null)}
          className="text-muted-foreground hover:text-foreground text-xs"
        >
          ✕
        </button>
      </div>

      {/* 颜色预览 */}
      <div className="flex items-center gap-2 mb-3">
        <div
          className="w-6 h-6 rounded border"
          style={{ backgroundColor: selectedBrick.color }}
        />
        <span className="text-sm text-muted-foreground">{selectedBrick.colorName}</span>
      </div>

      {/* 详细信息 */}
      <div className="space-y-1 text-xs text-muted-foreground">
        <p>编号: {selectedBrick.partId}</p>
        <p>
          尺寸: {selectedBrick.size.x}×{selectedBrick.size.z} (凸点)
        </p>
        <p>
          高度: {selectedBrick.size.y} 层
        </p>
        <p>
          位置: ({selectedBrick.position.x}, {selectedBrick.position.y},{" "}
          {selectedBrick.position.z})
        </p>
      </div>
    </div>
  )
}
