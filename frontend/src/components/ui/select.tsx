import * as React from "react"
import { cn } from "../../lib/utils"
import { ChevronDown, Check } from "lucide-react"

// ===== Context =====

interface SelectContextValue {
  value: string
  onValueChange: (value: string) => void
  open: boolean
  setOpen: (open: boolean) => void
}

const SelectContext = React.createContext<SelectContextValue | null>(null)

function useSelect() {
  const ctx = React.useContext(SelectContext)
  if (!ctx) throw new Error("Select components must be used within Select")
  return ctx
}

// ===== Select =====

interface SelectProps {
  value: string
  onValueChange: (value: string) => void
  children: React.ReactNode
  className?: string
}

const Select: React.FC<SelectProps> = ({ value, onValueChange, children, className }) => {
  const [open, setOpen] = React.useState(false)

  return (
    <SelectContext.Provider value={{ value, onValueChange, open, setOpen }}>
      <div className={cn("relative", className)}>{children}</div>
    </SelectContext.Provider>
  )
}

// ===== SelectTrigger =====

interface SelectTriggerProps {
  className?: string
  children: React.ReactNode
}

const SelectTrigger: React.FC<SelectTriggerProps> = ({ className, children }) => {
  const { setOpen } = useSelect()
  return (
    <button
      type="button"
      onClick={() => setOpen((prev) => !prev)}
      className={cn(
        "flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
        className
      )}
    >
      {children}
      <ChevronDown className="h-4 w-4 opacity-50" />
    </button>
  )
}

// ===== SelectValue =====

interface SelectValueProps {
  placeholder?: string
}

const SelectValue: React.FC<SelectValueProps> = ({ placeholder = "选择..." }) => {
  const { value } = useSelect()
  return <span>{value || placeholder}</span>
}

// ===== SelectContent =====

interface SelectContentProps {
  className?: string
  children: React.ReactNode
}

const SelectContent: React.FC<SelectContentProps> = ({ className, children }) => {
  const { open, setOpen } = useSelect()

  React.useEffect(() => {
    if (!open) return
    const handleClick = () => setOpen(false)
    document.addEventListener("click", handleClick)
    return () => document.removeEventListener("click", handleClick)
  }, [open, setOpen])

  if (!open) return null

  return (
    <div
      className={cn(
        "absolute z-50 mt-1 w-full min-w-[8rem] overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-md animate-in fade-in-80",
        className
      )}
      onClick={(e) => e.stopPropagation()}
    >
      <div className="p-1">{children}</div>
    </div>
  )
}

// ===== SelectItem =====

interface SelectItemProps {
  value: string
  className?: string
  children: React.ReactNode
}

const SelectItem: React.FC<SelectItemProps> = ({ value, className, children }) => {
  const { value: selectedValue, onValueChange, setOpen } = useSelect()
  const isSelected = value === selectedValue

  return (
    <div
      className={cn(
        "relative flex cursor-pointer select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none hover:bg-accent hover:text-accent-foreground",
        isSelected && "bg-accent",
        className
      )}
      onClick={() => {
        onValueChange(value)
        setOpen(false)
      }}
    >
      {isSelected && <Check className="absolute left-2 h-4 w-4" />}
      <span className={cn(isSelected && "pl-6")}>{children}</span>
    </div>
  )
}

export { Select, SelectTrigger, SelectValue, SelectContent, SelectItem }
