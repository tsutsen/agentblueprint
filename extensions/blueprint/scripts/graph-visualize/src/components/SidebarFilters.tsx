import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'

export interface SidebarFiltersProps {
  categories: Record<string, { count: number; color: string }>
  activeCategories: Set<string>
  onCategoryChange: (cat: string, checked: boolean) => void
}

export function SidebarFilters({ categories, activeCategories, onCategoryChange }: SidebarFiltersProps) {
  const allCount = Object.keys(categories).length
  const allSelected = activeCategories.size === allCount

  return (
    <div className="p-3 border-b border-border">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-[10px] uppercase tracking-wider text-muted-foreground">Categories</h3>
        <Button
          variant="ghost"
          size="sm"
          className="h-5 px-1.5 text-[10px]"
          onClick={() => onCategoryChange('__toggle_all__', !allSelected)}
        >
          {allSelected ? 'Deselect all' : 'Select all'}
        </Button>
      </div>
      <div className="space-y-0.5">
        {Object.entries(categories)
          .sort((a, b) => b[1].count - a[1].count)
          .map(([cat, { count, color }]) => (
            <label
              key={cat}
              className="flex items-center gap-2 p-1 rounded cursor-pointer hover:bg-muted/50 text-sm"
            >
              <Checkbox
                id={`cat-${cat}`}
                checked={activeCategories.has(cat)}
                onCheckedChange={(checked) => onCategoryChange(cat, checked === true)}
              />
              <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
              <span className="flex-1 truncate">{cat.charAt(0).toUpperCase() + cat.slice(1)}</span>
              <span className="text-xs text-muted-foreground font-mono">{count}</span>
            </label>
          ))}
      </div>
    </div>
  )
}
