import type { IGraphBridge } from '@/components/GraphCanvas'
import { themes } from '@/lib/themes'
import { SIZE_METRICS } from '@/lib/metrics'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { ChevronDown, ZoomIn, ZoomOut, RotateCcw } from 'lucide-react'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

export interface ControlsProps {
  bridge: IGraphBridge | null
  isSimulating: boolean
  onSimulationChange: (checked: boolean) => void
  sizeMetric: string
  onSizeMetricChange: (key: string) => void
  currentTheme: string
  onThemeChange: (key: string) => void
}

export function Controls({
  bridge,
  isSimulating,
  onSimulationChange,
  sizeMetric,
  onSizeMetricChange,
  currentTheme,
  onThemeChange,
}: ControlsProps) {
  return (
    <>
      {/* Top-left controls */}
      <div className="absolute top-3 left-3 flex items-start gap-1.5 z-10">
        <Tooltip>
          <TooltipTrigger asChild>
            <label className="inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md px-2 h-8 text-xs font-medium bg-background/90 backdrop-blur border border-input cursor-pointer graph-control-btn">
              Simulation
              <Switch
                checked={isSimulating}
                onCheckedChange={(checked) => {
                  if (checked) {
                    bridge?.startSimulation()
                  } else {
                    bridge?.stopSimulation()
                  }
                  onSimulationChange(checked)
                }}
              />
            </label>
          </TooltipTrigger>
        </Tooltip>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" className="h-8 text-xs bg-background backdrop-blur graph-control-btn">
              Size: {SIZE_METRICS.find((m) => m.key === sizeMetric)?.label}
              <ChevronDown className="h-3.5 w-3.5 ml-1" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            {SIZE_METRICS.map((m) => (
              <DropdownMenuItem
                key={m.key}
                onClick={() => {
                  bridge?.setSizeMetric(m.key)
                  onSizeMetricChange(m.key)
                }}
              >
                {m.label}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" className="h-8 text-xs bg-background backdrop-blur graph-control-btn">
              Theme: {themes.find((t) => t.key === currentTheme)?.label || 'Default'}
              <ChevronDown className="h-3.5 w-3.5 ml-1" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            {themes.map((t) => (
              <DropdownMenuItem
                key={t.key}
                onClick={() => {
                  bridge?.setTheme(t.key)
                  onThemeChange(t.key)
                }}
              >
                {t.label}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Zoom Controls — bottom left */}
      <div className="absolute bottom-3 left-3 flex items-center gap-1 z-10">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              className="h-8 w-8 p-0 bg-background backdrop-blur graph-control-btn"
              onClick={() => bridge?.zoomIn()}
            >
              <ZoomIn className="h-3.5 w-3.5" />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="top">Zoom in</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              className="h-8 w-8 p-0 bg-background backdrop-blur graph-control-btn"
              onClick={() => bridge?.zoomOut()}
            >
              <ZoomOut className="h-3.5 w-3.5" />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="top">Zoom out</TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              className="h-8 w-8 p-0 bg-background backdrop-blur graph-control-btn"
              onClick={() => bridge?.resetZoom()}
            >
              <RotateCcw className="h-3.5 w-3.5" />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="top">Reset zoom</TooltipContent>
        </Tooltip>
      </div>
    </>
  )
}
