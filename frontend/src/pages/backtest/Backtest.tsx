import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { LineChart, Play } from "lucide-react"

export function Backtest() {
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
            <CardContent className="h-[300px] flex items-center justify-center">
              <div className="flex flex-col items-center text-muted-foreground">
                <LineChart className="h-12 w-12 mb-4 opacity-50" />
                <p>Run a backtest to view results.</p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
