import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { ShieldAlert, AlertTriangle, CheckCircle2, Shield } from "lucide-react"
import { useMt5Account } from "@/api/hooks"

export function Risk() {
  const { data: mt5Account, isLoading } = useMt5Account();

  if (isLoading) {
    return <div className="text-muted-foreground p-6 font-mono text-sm">Loading risk profile...</div>;
  }

  if (!mt5Account) {
    return (
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Risk Analysis</h1>
          <p className="text-muted-foreground">Portfolio risk metrics and safety boundaries.</p>
        </div>
        <Card className="bg-[#09090b] border-white/5 shadow-none">
          <CardHeader>
            <CardTitle>Not Connected</CardTitle>
            <CardDescription>Connect to an MT5 account to view live risk metrics.</CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  // Calculate live risk metrics
  const floatingPL = mt5Account.equity - mt5Account.balance;
  const isDrawdown = floatingPL < 0;
  const drawdownPercent = isDrawdown ? (Math.abs(floatingPL) / mt5Account.balance) * 100 : 0;
  const dailyLossLimit = 5.0; // 5% standard limit
  
  const isBreaching = drawdownPercent >= dailyLossLimit;
  const isWarning = drawdownPercent >= (dailyLossLimit * 0.8);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Risk Analysis</h1>
        <p className="text-muted-foreground">Portfolio risk metrics and safety boundaries.</p>
      </div>

      {isBreaching ? (
        <Alert variant="destructive" className="bg-red-500/10 border-red-500/20 text-red-500">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Max Drawdown Breached</AlertTitle>
          <AlertDescription>
            Account has breached the {dailyLossLimit}% daily drawdown limit. Current drawdown: {drawdownPercent.toFixed(2)}%.
          </AlertDescription>
        </Alert>
      ) : isWarning ? (
        <Alert className="bg-yellow-500/10 border-yellow-500/20 text-yellow-500">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Drawdown Warning</AlertTitle>
          <AlertDescription>
            Account is approaching the {dailyLossLimit}% daily limit. Current drawdown: {drawdownPercent.toFixed(2)}%.
          </AlertDescription>
        </Alert>
      ) : (
        <Alert className="bg-green-500/10 border-green-500/20 text-green-500">
          <CheckCircle2 className="h-4 w-4 text-green-500" />
          <AlertTitle>Risk Parameters Safe</AlertTitle>
          <AlertDescription>
            Account is operating within safe drawdown limits.
          </AlertDescription>
        </Alert>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        <Card className="bg-[#09090b] border-white/5 shadow-none">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-zinc-300">Live Drawdown</CardTitle>
            <ShieldAlert className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${isDrawdown ? 'text-red-500' : 'text-green-500'}`}>
              {drawdownPercent.toFixed(2)}%
            </div>
            <p className="text-xs text-muted-foreground">Limit: {dailyLossLimit}%</p>
          </CardContent>
        </Card>
        
        <Card className="bg-[#09090b] border-white/5 shadow-none">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-zinc-300">Margin Level</CardTitle>
            <Shield className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-zinc-100">
              {mt5Account.margin > 0 ? ((mt5Account.equity / mt5Account.margin) * 100).toFixed(2) + '%' : 'N/A'}
            </div>
            <p className="text-xs text-muted-foreground">Free Margin: ${mt5Account.margin_free.toLocaleString()}</p>
          </CardContent>
        </Card>

        <Card className="bg-[#09090b] border-white/5 shadow-none">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-zinc-300">Account Leverage</CardTitle>
            <Shield className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-zinc-100">
              1:{mt5Account.leverage}
            </div>
            <p className="text-xs text-muted-foreground">Broker constraint</p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
