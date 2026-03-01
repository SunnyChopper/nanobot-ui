/**
 * Tooltip — atomic component for hover/focus help text.
 * Use to hide repetitive hints while keeping them available on demand.
 */

import { useState, useId } from 'react'

export interface TooltipProps {
  /** Trigger element (e.g. icon or label). Receives aria-describedby from content. */
  children: React.ReactNode
  /** Text shown in the tooltip. */
  content: string
  /** Optional class for the wrapper. */
  className?: string
}

export function Tooltip({ children, content, className = '' }: TooltipProps) {
  const [visible, setVisible] = useState(false)
  const id = useId()

  return (
    <span
      className={`relative inline-flex ${className}`}
      aria-describedby={visible ? id : undefined}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocusCapture={(e) => {
        if (e.target !== e.currentTarget) setVisible(true)
      }}
      onBlurCapture={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget)) setVisible(false)
      }}
    >
      {children}
      {visible && content && (
        <span
          id={id}
          role="tooltip"
          className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 px-2 py-1.5 text-xs text-zinc-200 bg-zinc-800 border border-zinc-600 rounded shadow-lg whitespace-normal max-w-[240px] z-50 pointer-events-none"
        >
          {content}
        </span>
      )}
    </span>
  )
}
