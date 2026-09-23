import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { BarChart2, Play } from "lucide-react"

export function PropSim() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Prop-Firm Simulator</h1>
          <p className="text-muted-foreground">Validate models against strict firm challenge rules.</p>
        </div>
        <Button>
          <Play data-icon="inline-start" />
          Run Simulation
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Challenge Results</CardTitle>
          <CardDescription>Evaluation of backtests against prop-firm profiles.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center h-[400px] border border-dashed rounded-md gap-4">
            <BarChart2 className="h-10 w-10 text-muted-foreground" />
            <div className="text-center">
              <h3 className="text-lg font-medium">No simulation results</h3>
              <p className="text-sm text-muted-foreground mt-1">Run a simulation to see challenge pass/fail status.</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
