import { forwardRef } from 'react'
import { Input } from '@/components/ui/input'
import { Kbd } from '@/components/ui/kbd'
import { Search } from 'lucide-react'

export interface SidebarSearchProps {
  value: string
  onChange: (value: string) => void
}

export const SidebarSearch = forwardRef<HTMLInputElement, SidebarSearchProps>(function SidebarSearch({ value, onChange }, ref) {
  return (
    <div className="p-3 border-b border-border">
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          ref={ref}
          placeholder="Search nodes..."
          className="pl-9 h-8 text-sm"
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
        <Kbd className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none">K</Kbd>
      </div>
    </div>
  )
})
