import * as React from "react"
import { cn } from "../../lib/utils"

interface TabsProps {
  tabs: { id: string; label: string }[]
  activeTab: string
  onTabChange: (id: string) => void
  className?: string
}

const Tabs: React.FC<TabsProps> = ({ tabs, activeTab, onTabChange, className }) => {
  return (
    <div className={cn("flex space-x-1 rounded-lg bg-muted p-1", className)}>
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          className={cn(
            "flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-all",
            activeTab === tab.id
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}

export { Tabs }
