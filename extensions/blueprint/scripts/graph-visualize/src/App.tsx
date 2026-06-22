import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import { Search, RotateCcw, Play, Settings, ChevronDown } from 'lucide-react'

function App() {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background text-foreground">
      {/* Sidebar */}
      <aside className="w-[300px] min-w-[300px] flex flex-col border-r border-border bg-muted/30">
        {/* Header */}
        <div className="p-4 border-b border-border">
          <h1 className="text-sm font-bold text-foreground">Glossary Graph</h1>
          <p className="text-xs text-muted-foreground mt-0.5">Architecture knowledge map</p>
        </div>

        {/* Search */}
        <div className="p-3 border-b border-border">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input placeholder="Search nodes..." className="pl-9 h-8 text-sm" />
          </div>
        </div>

        {/* Filters */}
        <div className="p-3 border-b border-border">
          <h3 className="text-[10px] uppercase tracking-wider text-muted-foreground mb-2">Categories</h3>
          <div className="space-y-1">
            <label className="flex items-center gap-2 p-1 rounded cursor-pointer hover:bg-muted/50 text-sm">
              <Checkbox id="domain" defaultChecked />
              <span className="w-2 h-2 rounded-full bg-[#f472b6] flex-shrink-0" />
              <span>Domain</span>
              <span className="ml-auto text-xs text-muted-foreground font-mono">42</span>
            </label>
            <label className="flex items-center gap-2 p-1 rounded cursor-pointer hover:bg-muted/50 text-sm">
              <Checkbox id="technical" defaultChecked />
              <span className="w-2 h-2 rounded-full bg-[#38bdf8] flex-shrink-0" />
              <span>Technical</span>
              <span className="ml-auto text-xs text-muted-foreground font-mono">28</span>
            </label>
            <label className="flex items-center gap-2 p-1 rounded cursor-pointer hover:bg-muted/50 text-sm">
              <Checkbox id="security" defaultChecked />
              <span className="w-2 h-2 rounded-full bg-[#fbbf24] flex-shrink-0" />
              <span>Security</span>
              <span className="ml-auto text-xs text-muted-foreground font-mono">15</span>
            </label>
          </div>
        </div>

        {/* Node List */}
        <ScrollArea className="flex-1 p-1">
          <div className="space-y-0.5">
            {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((i) => (
              <button key={i} className="w-full flex items-center gap-2 px-2 py-1 rounded text-sm hover:bg-muted/50 text-left">
                <span className="truncate font-medium text-foreground">Example Node {i}</span>
                <Badge variant="secondary" className="text-[10px] flex-shrink-0 font-mono">T{i}</Badge>
              </button>
            ))}
          </div>
        </ScrollArea>
      </aside>

      {/* Main Canvas Area */}
      <main className="flex-1 relative overflow-hidden">
        {/* Controls */}
        <div className="absolute top-3 left-3 flex items-start gap-1.5 z-10">
          <Button variant="outline" size="sm" className="h-8 text-xs">
            <RotateCcw className="h-3.5 w-3.5 mr-1" />
            Reset Zoom
          </Button>
          <Button variant="outline" size="sm" className="h-8 text-xs">
            <Play className="h-3.5 w-3.5 mr-1" />
            Simulate
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="h-8 text-xs">
                Size: Degree
                <ChevronDown className="h-3.5 w-3.5 ml-1" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              <DropdownMenuItem>Degree</DropdownMenuItem>
              <DropdownMenuItem>Blast Radius</DropdownMenuItem>
              <DropdownMenuItem>Risk Score</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="h-8 text-xs">
                <Settings className="h-3.5 w-3.5 mr-1" />
                Theme
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              <DropdownMenuItem>Dark</DropdownMenuItem>
              <DropdownMenuItem>Light</DropdownMenuItem>
              <DropdownMenuItem>Gruvbox</DropdownMenuItem>
              <DropdownMenuItem>Neon</DropdownMenuItem>
              <DropdownMenuItem>Retro</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Canvas placeholder */}
        <div className="w-full h-full bg-background flex items-center justify-center">
          <div className="text-center space-y-3">
            <Skeleton className="h-4 w-48 mx-auto" />
            <Skeleton className="h-4 w-64 mx-auto" />
            <p className="text-xs text-muted-foreground">Canvas bridge coming in Phase 2</p>
          </div>
        </div>
      </main>

      {/* Detail Panel (Sheet) */}
      <Sheet>
        <SheetContent side="right" className="w-[380px] sm:w-[380px]">
          <SheetHeader>
            <SheetTitle className="text-base">
              <div className="flex flex-col gap-1">
                <span>Example Node</span>
                <div className="flex items-center gap-2">
                  <Badge variant="secondary" className="text-[10px] uppercase">Domain</Badge>
                  <span className="text-xs text-muted-foreground font-mono">REQ-001</span>
                </div>
              </div>
            </SheetTitle>
          </SheetHeader>
          <Separator className="my-3" />
          <div className="space-y-3">
            <p className="text-sm leading-relaxed text-muted-foreground">
              This is an example node description that would appear in the detail panel.
              The actual content comes from graph-data.json.
            </p>
            <div className="text-xs text-muted-foreground space-y-1 border-t border-border pt-3">
              <div><strong className="text-foreground">Connections:</strong> 5</div>
              <div><strong className="text-foreground">Degree:</strong> 8</div>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  )
}

export default App
