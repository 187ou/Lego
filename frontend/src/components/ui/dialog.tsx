import * as React from "react"
import { cn } from "../../lib/utils"
import { X } from "lucide-react"

interface DialogProps {
  open: boolean
  onClose: () => void
  children: React.ReactNode
  className?: string
}

const Dialog: React.FC<DialogProps> = ({ open, onClose, children, className }) => {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="fixed inset-0 bg-black/50" onClick={onClose} />
      <div
        className={cn(
          "relative z-50 w-full max-w-lg rounded-lg bg-background p-6 shadow-xl animate-fade-in",
          className
        )}
      >
        <button
          onClick={onClose}
          className="absolute right-4 top-4 rounded-sm opacity-70 hover:opacity-100"
        >
          <X className="h-4 w-4" />
        </button>
        {children}
      </div>
    </div>
  )
}

const DialogTitle: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className,
}) => <h2 className={cn("text-lg font-semibold mb-4", className)}>{children}</h2>

export { Dialog, DialogTitle }
