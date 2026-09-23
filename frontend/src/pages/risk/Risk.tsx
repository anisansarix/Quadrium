import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { ShieldAlert, AlertTriangle, CheckCircle2 } from "lucide-react"

export function Risk() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Risk Analysis</h1>
        <p className="text-muted-foreground">Portfolio risk metrics and safety boundaries.</p>
      </div>

      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertTitle>Max Drawdown Warning</AlertTitle>
        <AlertDescription>
          Model v4.1 breached the 5% daily drawdown limit during backtest on 2023-04-15.
        </AlertDescription>
      </Alert>
      
      <Alert>
        <CheckCircle2 className="h-4 w-4 text-primary" />
        <AlertTitle>Prop-Firm Compliant</AlertTitle>
        <AlertDescription>
          Model v5.2 passed all FTMO challenge constraints.
        </AlertDescription>
      </Alert>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Daily Drawdown</CardTitle>
            <ShieldAlert className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">2.4%</div>
            <p className="text-xs text-muted-foreground">Limit: 5.0%</p>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Max Drawdown</CardTitle>
            <ShieldAlert className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">8.1%</div>
            <p className="text-xs text-muted-foreground">Limit: 10.0%</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Margin Utilization</CardTitle>
            <ShieldAlert className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">42%</div>
            <p className="text-xs text-muted-foreground">Healthy</p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
