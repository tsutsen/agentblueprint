import { cn } from '@/lib/utils'
import type { HTMLAttributes } from 'react'

export interface KbdProps extends HTMLAttributes<HTMLElement> {
  children: React.ReactNode
}

export function Kbd({ className, children, ...props }: KbdProps) {
  return (
    <kbd
      className={cn(
        'inline-flex h-4 items-center rounded border border-border bg-muted px-1 font-mono text-[10px] text-muted-foreground',
        className,
      )}
      {...props}
    >
      {children}
    </kbd>
  )
}
