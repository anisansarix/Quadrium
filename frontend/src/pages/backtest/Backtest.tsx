import { useEffect, useRef } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Play } from "lucide-react"
import { createChart, ColorType } from "lightweight-charts"

export function Backtest() {
  const chartContainerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!chartContainerRef.current) return

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#888',
      },
      grid: {
        vertLines: { color: '#333' },
        horzLines: { color: '#333' },
      },
      width: chartContainerRef.current.clientWidth,
      height: 350,
    })

    const lineSeries = chart.addLineSeries({ color: '#2962FF' })
    
    // Dummy data for now
    lineSeries.setData([
      { time: '2024-01-01', value: 10000 },
      { time: '2024-01-02', value: 10050 },
      { time: '2024-01-03', value: 9980 },
      { time: '2024-01-04', value: 10120 },
      { time: '2024-01-05', value: 10250 },
      { time: '2024-01-06', value: 10200 },
      { time: '2024-01-07', value: 10400 },
    ])

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth })
      }
    }

    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      chart.remove()
    }
  }, [])

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Backtesting</h1>
          <p className="text-muted-foreground">Run models against historical data.</p>
        </div>
        <Button>
          <Play className="mr-2 h-4 w-4" />
          Run Backtest
        </Button>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <div className="md:col-span-1 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Configuration</CardTitle>
              <CardDescription>Select model and dataset.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Model</label>
                  <div className="h-10 border rounded-md px-3 flex items-center text-sm text-muted-foreground">
                    Select a model...
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">Dataset</label>
                  <div className="h-10 border rounded-md px-3 flex items-center text-sm text-muted-foreground">
                    Select a dataset...
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="md:col-span-2 space-y-6">
          <Card className="h-full min-h-[400px]">
            <CardHeader>
              <CardTitle>Equity Curve</CardTitle>
              <CardDescription>Cumulative returns over time.</CardDescription>
            </CardHeader>
            <CardContent>
              <div ref={chartContainerRef} className="w-full" />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
