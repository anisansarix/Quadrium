import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  TrendingUp,
  DollarSign,
  Activity,
  AlertCircle,
  Shield,
  BrainCircuit,
} from "lucide-react";
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
} from "@/components/ui/chart";
import type { ChartConfig } from "@/components/ui/chart";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useState } from "react";
import { Label } from "@/components/ui/label";
import { Play, Loader2 } from "lucide-react";
import {
  useSystemHealth,
  useMt5Account,
  useExperiments,
  useStartLiveSession,
  useLiveSessions,
  useMt5Positions,
  useSystemLogs,
} from "@/api/hooks";

const chartConfig = {
  balance: {
    label: "Account Balance",
    color: "#f97316",
  },
} satisfies ChartConfig;

const recentTrades = [
  {
    id: "T-8921",
    date: "2026-03-24 14:20",
    pair: "XAUUSD",
    type: "Buy",
    lots: 5.0,
    open: 2154.3,
    close: 2158.5,
    pl: 2100.0,
    status: "win",
  },
  {
    id: "T-8920",
    date: "2026-03-24 10:15",
    pair: "EURUSD",
    type: "Sell",
    lots: 10.0,
    open: 1.0854,
    close: 1.0865,
    pl: -1100.0,
    status: "loss",
  },
  {
    id: "T-8919",
    date: "2026-03-23 16:45",
    pair: "US30",
    type: "Buy",
    lots: 2.0,
    open: 39150,
    close: 39220,
    pl: 1400.0,
    status: "win",
  },
  {
    id: "T-8918",
    date: "2026-03-23 09:30",
    pair: "GBPUSD",
    type: "Buy",
    lots: 5.0,
    open: 1.264,
    close: 1.2655,
    pl: 750.0,
    status: "win",
  },
  {
    id: "T-8917",
    date: "2026-03-22 13:10",
    pair: "BTCUSD",
    type: "Sell",
    lots: 1.0,
    open: 65400,
    close: 65100,
    pl: 300.0,
    status: "win",
  },
];

export default function Dashboard() {
  const { data: health, isLoading } = useSystemHealth();
  const { data: mt5Account } = useMt5Account();
  const { data: systemLogs } = useSystemLogs();
  const { data: experiments } = useExperiments();
  const startLiveSession = useStartLiveSession();
  const { data: liveSessions } = useLiveSessions();
  const activeSessionId =
    liveSessions?.find((s) => s.status === "running" || s.status === "active")
      ?.id || "default";
  
  const activeSession = liveSessions?.find((s) => s.id === activeSessionId && s.id !== "default");
  const prediction = activeSession?.config?.latest_prediction || 0;
  const predictionPercent = ((prediction + 1) / 2) * 100;
  
  let agentAction = "NEUTRAL (HOLD)";
  let actionColor = "text-zinc-400";
  if (prediction > 0.5) { agentAction = "BUY (LONG)"; actionColor = "text-green-500"; }
  else if (prediction < -0.5) { agentAction = "SELL (SHORT)"; actionColor = "text-red-500"; }

  const { data: positions } = useMt5Positions(activeSessionId);

  const [experimentId, setExperimentId] = useState("");
  const [symbol, setSymbol] = useState("XAUUSD");
  const [timeframe, setTimeframe] = useState("M5");
  const [riskPercent, setRiskPercent] = useState("0.5");
  const [autoRisk, setAutoRisk] = useState(true);

  const handleStartSession = () => {
    if (!experimentId) return;
    startLiveSession.mutate(
      {
        experiment_id: experimentId,
        symbol,
        timeframe,
        config: { risk_percent: parseFloat(riskPercent), auto_risk: autoRisk },
      },
      {
        onSuccess: () => {
          setExperimentId("");
        },
      },
    );
  };

  const getStatusColor = (isOnline: boolean | undefined, loading: boolean) => {
    if (loading) return "bg-yellow-500 shadow-[0_0_8px_rgba(234,179,8,0.6)]";
    return isOnline
      ? "bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]"
      : "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)]";
  };

  const balance = mt5Account?.balance || 0;
  const equity = mt5Account?.equity || 0;
  const freeMargin = mt5Account?.margin_free || 0;
  const marginLevel =
    mt5Account?.margin && mt5Account.margin > 0
      ? (equity / mt5Account.margin) * 100
      : 0;

  const formattedBalance = `$${balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  const formattedEquity = `$${equity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  const formattedFreeMargin = `$${freeMargin.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  const floatingPL = equity - balance;

  const initialBalance = balance || 100000;

  // Dynamic Chart Data from Live Sessions history
  const dynamicChartData =
    liveSessions && liveSessions.length > 0
      ? [...liveSessions].reverse().map((s) => ({
          day: new Date(s.created_at).toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
          }),
          balance: s.current_balance,
        }))
      : [
          { day: "Day 1", balance: 100000 },
          { day: "Day 2", balance: 100500 },
          { day: "Day 3", balance: 99800 },
          { day: "Day 4", balance: 101200 },
          { day: "Day 5", balance: 102500 },
        ];

  // Profit Target (8%)
  const profitTargetGoal = initialBalance * 0.08;
  const currentProfit = Math.max(0, equity - initialBalance);
  const profitTargetPct =
    profitTargetGoal > 0
      ? Math.min(100, (currentProfit / profitTargetGoal) * 100)
      : 0;

  // Max Daily Loss (5%)
  const dailyLossLimit = initialBalance * 0.05;
  const currentLoss = Math.max(0, initialBalance - equity);
  const dailyLossPct =
    dailyLossLimit > 0
      ? Math.min(100, (currentLoss / dailyLossLimit) * 100)
      : 0;

  return (
    <div className="mx-auto max-w-[1600px] space-y-3">
      {/* Account Details & Services Panel */}
      <Card className="flex flex-col lg:flex-row justify-between items-center p-3 px-4 gap-4 rounded-md">
        {/* Left: Account Details */}
        <div className="flex flex-wrap items-center gap-10 text-sm">
          <div className="flex flex-col">
            <span className="text-muted-foreground text-xs uppercase font-medium tracking-wider">
              Balance
            </span>
            <span className="font-bold font-mono text-lg">
              {formattedBalance}
            </span>
          </div>
          <div className="flex flex-col">
            <span className="text-muted-foreground text-xs uppercase font-medium tracking-wider">
              Equity
            </span>
            <span className="font-bold font-mono text-lg">
              {formattedEquity}
            </span>
          </div>
          <div className="flex flex-col">
            <span className="text-muted-foreground text-xs uppercase font-medium tracking-wider">
              Free Margin
            </span>
            <span className="font-bold font-mono text-lg">
              {formattedFreeMargin}
            </span>
          </div>
          <div className="flex flex-col">
            <span className="text-muted-foreground text-xs uppercase font-medium tracking-wider">
              Margin Level
            </span>
            <span
              className={`font-bold font-mono text-lg ${marginLevel < 100 && marginLevel > 0 ? "text-red-500" : "text-green-500"}`}
            >
              {marginLevel > 0 ? `${marginLevel.toFixed(2)}%` : "N/A"}
            </span>
          </div>
        </div>

        {/* Right: Service Statuses */}
        <div className="grid grid-cols-2 gap-2">
          <Badge
            variant="outline"
            className="bg-background/50 border-border/50 py-0.5 px-2 text-[10px] shadow-sm rounded-sm justify-start"
          >
            <span
              className={`w-1.5 h-1.5 rounded-full mr-1.5 ${getStatusColor(health?.duckdb_connected, isLoading)}`}
            />{" "}
            DuckDB
          </Badge>
          <Badge
            variant="outline"
            className="bg-background/50 border-border/50 py-0.5 px-2 text-[10px] shadow-sm rounded-sm justify-start"
          >
            <span
              className={`w-1.5 h-1.5 rounded-full mr-1.5 ${getStatusColor(health?.sqlite_connected, isLoading)}`}
            />{" "}
            SQLite
          </Badge>
          <Badge
            variant="outline"
            className="bg-background/50 border-border/50 py-0.5 px-2 text-[10px] shadow-sm rounded-sm justify-start"
          >
            <span
              className={`w-1.5 h-1.5 rounded-full mr-1.5 ${getStatusColor(health?.status === "ok", isLoading)}`}
            />{" "}
            FastAPI
          </Badge>
          <Badge
            variant="outline"
            className="bg-background/50 border-border/50 py-0.5 px-2 text-[10px] shadow-sm rounded-sm justify-start"
          >
            <span
              className={`w-1.5 h-1.5 rounded-full mr-1.5 ${getStatusColor(!!mt5Account, isLoading)}`}
            />{" "}
            MT5
          </Badge>
        </div>
      </Card>

      {/* Top KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        <Card className="bg-card rounded-md">
          <CardHeader className="flex flex-row items-center justify-between pb-1 pt-3 px-4">
            <CardTitle className="text-[11px] font-medium text-muted-foreground uppercase tracking-widest">
              Current Balance
            </CardTitle>
            <DollarSign className="w-3 h-3 text-primary" />
          </CardHeader>
          <CardContent className="px-4 pb-3">
            <div className="text-xl font-bold tabular-nums">
              {formattedBalance}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Live MT5 Account
            </p>
          </CardContent>
        </Card>

        <Card className="bg-card rounded-md">
          <CardHeader className="flex flex-row items-center justify-between pb-1 pt-3 px-4">
            <CardTitle className="text-[11px] font-medium text-muted-foreground uppercase tracking-widest">
              Current Equity
            </CardTitle>
            <Activity className="w-3 h-3 text-primary" />
          </CardHeader>
          <CardContent className="px-4 pb-3">
            <div className="text-xl font-bold tabular-nums">
              {formattedEquity}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Floating P/L:{" "}
              <span
                className={`font-medium ${floatingPL >= 0 ? "text-green-500" : "text-red-500"}`}
              >
                {floatingPL >= 0 ? "+" : ""}${floatingPL.toFixed(2)}
              </span>
            </p>
          </CardContent>
        </Card>

        <Card className="bg-card rounded-md">
          <CardHeader className="flex flex-row items-center justify-between pb-1 pt-3 px-4">
            <CardTitle className="text-[11px] font-medium text-muted-foreground uppercase tracking-widest">
              Profit Target (8%)
            </CardTitle>
            <TrendingUp className="w-3 h-3 text-primary" />
          </CardHeader>
          <CardContent className="px-4 pb-3">
            <div className="text-xl font-bold tabular-nums">
              $
              {currentProfit.toLocaleString(undefined, {
                minimumFractionDigits: 0,
                maximumFractionDigits: 0,
              })}{" "}
              <span className="text-sm font-normal text-muted-foreground">
                / ${profitTargetGoal.toLocaleString()}
              </span>
            </div>
            <Progress value={profitTargetPct} className="h-2 mt-3" />
            <p className="text-xs text-muted-foreground mt-2">
              {profitTargetPct.toFixed(1)}% completed
            </p>
          </CardContent>
        </Card>

        <Card className="bg-card rounded-md">
          <CardHeader className="flex flex-row items-center justify-between pb-1 pt-3 px-4">
            <CardTitle className="text-[11px] font-medium text-muted-foreground uppercase tracking-widest">
              Max Daily Loss (5%)
            </CardTitle>
            <AlertCircle className="w-3 h-3 text-orange-500" />
          </CardHeader>
          <CardContent className="px-4 pb-3">
            <div className="text-xl font-bold tabular-nums">
              $
              {currentLoss.toLocaleString(undefined, {
                minimumFractionDigits: 0,
                maximumFractionDigits: 0,
              })}{" "}
              <span className="text-sm font-normal text-muted-foreground">
                / ${dailyLossLimit.toLocaleString()}
              </span>
            </div>
            <Progress
              value={dailyLossPct}
              className="h-2 mt-3 [&>div]:bg-orange-500"
            />
            <p className="text-xs text-muted-foreground mt-2">
              Resets at midnight
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Trade Session & Logs */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <Card className="bg-[#18181b] border-white/5 rounded-xl lg:col-span-1 shadow-lg">
          <CardHeader className="pb-4 pt-5 px-5">
            <CardTitle className="text-sm font-bold text-zinc-100 tracking-wide font-sans">
              Start New Session
            </CardTitle>
            <CardDescription className="text-xs text-zinc-400 mt-1">
              Deploy a trained model to the market
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 px-5 pb-5">
            <div className="space-y-1.5">
              <Label className="text-[12px] font-semibold text-zinc-200">
                Model (Experiment ID)
              </Label>
              <Select
                value={experimentId}
                onValueChange={(val) => val && setExperimentId(val)}
              >
                <SelectTrigger className="w-full h-9 bg-[#27272a] border-white/5 text-xs text-zinc-300 rounded-md font-medium">
                  <SelectValue placeholder="Select a model" />
                </SelectTrigger>
                <SelectContent>
                  {experiments?.map((exp) => (
                    <SelectItem key={exp.id} value={exp.id}>
                      {exp.name || exp.id}
                    </SelectItem>
                  ))}
                  {/* Fallback models for UI testing if DB is empty */}
                  <SelectItem value="xauusd_full_scale_rl_1yr">
                    xauusd_full_scale_rl_1yr
                  </SelectItem>
                  <SelectItem value="hft_scalper_v4">HFT Scalper V4</SelectItem>
                  <SelectItem value="grid_volatility_bot">
                    Volatility Grid Bot
                  </SelectItem>
                  <SelectItem value="trend_follower">Trend Follower</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-[12px] font-semibold text-zinc-200">
                  Symbol
                </Label>
                <Select
                  value={symbol}
                  onValueChange={(val) => val && setSymbol(val)}
                >
                  <SelectTrigger className="w-full h-9 bg-[#27272a] border-white/5 text-xs text-zinc-300 rounded-md font-medium">
                    <SelectValue placeholder="Symbol" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="xauusd">XAUUSD</SelectItem>
                    <SelectItem value="eurusd">EURUSD</SelectItem>
                    <SelectItem value="us30">US30</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-[12px] font-semibold text-zinc-200">
                  Timeframe
                </Label>
                <Select
                  value={timeframe}
                  onValueChange={(val) => val && setTimeframe(val)}
                >
                  <SelectTrigger className="w-full h-9 bg-[#27272a] border-white/5 text-xs text-zinc-300 rounded-md font-medium">
                    <SelectValue placeholder="Timeframe" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="m5">M5</SelectItem>
                    <SelectItem value="m15">M15</SelectItem>
                    <SelectItem value="h1">H1</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2 pt-1">
              <div className="flex items-center justify-between">
                <Label className="text-[12px] font-semibold text-zinc-200">
                  Risk Per Trade (%)
                </Label>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-medium text-zinc-400">
                    Manual
                  </span>
                  <Switch
                    checked={autoRisk}
                    onCheckedChange={setAutoRisk}
                    className="data-[state=checked]:bg-[#78b30a]"
                  />
                  <span className="text-[10px] font-medium text-zinc-400">
                    Auto
                  </span>
                </div>
              </div>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Shield className="h-3.5 w-3.5 text-zinc-500" />
                </div>
                <Input
                  value={riskPercent}
                  onChange={(e) => setRiskPercent(e.target.value)}
                  disabled={autoRisk}
                  className="w-full h-9 bg-[#27272a] border-white/5 text-xs text-zinc-300 rounded-md pl-8 font-medium disabled:opacity-50"
                />
              </div>
            </div>

            <Button
              onClick={handleStartSession}
              disabled={!experimentId || startLiveSession.isPending}
              className={`w-full mt-4 font-semibold rounded-full gap-2 h-10 text-xs shadow-none border-0 ${
                experimentId
                  ? "bg-[#78b30a] hover:bg-[#659905] text-white"
                  : "bg-[#24360b] hover:bg-[#2f460e] text-[#5e8b13]"
              }`}
            >
              {startLiveSession.isPending ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Play
                  className={`w-3.5 h-3.5 ${experimentId ? "fill-white" : "fill-[#5e8b13]"}`}
                />
              )}
              {startLiveSession.isPending ? "Starting..." : "Start Session"}
            </Button>
          </CardContent>
        </Card>

        {/* Trades Panel */}
        <Card className="bg-[#18181b] border-white/5 rounded-xl lg:col-span-2 shadow-lg flex flex-col">
          <CardHeader className="pb-4 pt-5 px-5">
            <CardTitle className="text-sm font-bold text-zinc-100 tracking-wide font-sans">
              Trades
            </CardTitle>
            <CardDescription className="text-xs text-zinc-400 mt-1">
              View your active positions and past trade history.
            </CardDescription>
          </CardHeader>
          <CardContent className="px-5 pb-5 flex-1 overflow-auto max-h-[350px] no-scrollbar">
            <Tabs defaultValue="open" className="w-full">
              <TabsList className="grid w-full max-w-[400px] grid-cols-2 mb-6 bg-[#27272a] text-zinc-400 rounded-md">
                <TabsTrigger
                  value="open"
                  className="text-xs data-[state=active]:bg-[#3f3f46] data-[state=active]:text-zinc-100 rounded-sm"
                >
                  Open Trade
                </TabsTrigger>
                <TabsTrigger
                  value="history"
                  className="text-xs data-[state=active]:bg-[#3f3f46] data-[state=active]:text-zinc-100 rounded-sm"
                >
                  History
                </TabsTrigger>
              </TabsList>

              <TabsContent value="open" className="m-0">
                <div className="rounded-md border border-white/5 overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow className="border-white/5 hover:bg-transparent">
                        <TableHead className="text-zinc-400 text-xs">
                          Trade ID
                        </TableHead>
                        <TableHead className="text-zinc-400 text-xs">
                          Date & Time
                        </TableHead>
                        <TableHead className="text-zinc-400 text-xs">
                          Symbol
                        </TableHead>
                        <TableHead className="text-zinc-400 text-xs">
                          Type
                        </TableHead>
                        <TableHead className="text-zinc-400 text-right text-xs">
                          Size (Lots)
                        </TableHead>
                        <TableHead className="text-zinc-400 text-right text-xs">
                          Open Price
                        </TableHead>
                        <TableHead className="text-zinc-400 text-right text-xs">
                          Current Price
                        </TableHead>
                        <TableHead className="text-zinc-400 text-right text-xs">
                          Floating P/L
                        </TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {positions && positions.length > 0 ? (
                        positions.map((trade) => (
                          <TableRow
                            key={trade.ticket}
                            className="border-white/5 hover:bg-white/5"
                          >
                            <TableCell className="font-mono text-[11px] text-zinc-300">
                              {trade.ticket}
                            </TableCell>
                            <TableCell className="text-zinc-500 text-[11px]">
                              {new Date(trade.time * 1000).toLocaleString()}
                            </TableCell>
                            <TableCell className="font-medium text-xs text-zinc-200">
                              {trade.symbol}
                            </TableCell>
                            <TableCell>
                              <Badge
                                variant="outline"
                                className={`text-[10px] px-1.5 py-0 ${trade.type === "Buy" || trade.type === "0" ? "text-blue-400 border-blue-400/20 bg-blue-400/10" : "text-orange-400 border-orange-400/20 bg-orange-400/10"}`}
                              >
                                {trade.type === "0" || trade.type === "Buy"
                                  ? "Buy"
                                  : "Sell"}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-right text-xs text-zinc-300">
                              {trade.volume.toFixed(2)}
                            </TableCell>
                            <TableCell className="text-right font-mono text-xs text-zinc-300">
                              {trade.price_open.toFixed(5)}
                            </TableCell>
                            <TableCell className="text-right font-mono text-xs text-zinc-300">
                              {trade.price_current.toFixed(5)}
                            </TableCell>
                            <TableCell
                              className={`text-right font-bold text-xs ${trade.profit >= 0 ? "text-[#78b30a]" : "text-red-500"}`}
                            >
                              {trade.profit >= 0 ? "+" : ""}$
                              {trade.profit.toFixed(2)}
                            </TableCell>
                          </TableRow>
                        ))
                      ) : (
                        <TableRow>
                          <TableCell
                            colSpan={8}
                            className="text-center text-zinc-500 py-8"
                          >
                            No open trades found
                          </TableCell>
                        </TableRow>
                      )}
                    </TableBody>
                  </Table>
                </div>
              </TabsContent>

              <TabsContent value="history" className="m-0">
                <div className="rounded-md border border-white/5 overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow className="border-white/5 hover:bg-transparent">
                        <TableHead className="text-zinc-400 text-xs">
                          Trade ID
                        </TableHead>
                        <TableHead className="text-zinc-400 text-xs">
                          Date & Time
                        </TableHead>
                        <TableHead className="text-zinc-400 text-xs">
                          Symbol
                        </TableHead>
                        <TableHead className="text-zinc-400 text-xs">
                          Type
                        </TableHead>
                        <TableHead className="text-zinc-400 text-right text-xs">
                          Size (Lots)
                        </TableHead>
                        <TableHead className="text-zinc-400 text-right text-xs">
                          Open Price
                        </TableHead>
                        <TableHead className="text-zinc-400 text-right text-xs">
                          Close Price
                        </TableHead>
                        <TableHead className="text-zinc-400 text-right text-xs">
                          Profit / Loss
                        </TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {recentTrades.map((trade) => (
                        <TableRow
                          key={trade.id}
                          className="border-white/5 hover:bg-white/5"
                        >
                          <TableCell className="font-mono text-[11px] text-zinc-300">
                            {trade.id}
                          </TableCell>
                          <TableCell className="text-zinc-500 text-[11px]">
                            {trade.date}
                          </TableCell>
                          <TableCell className="font-medium text-xs text-zinc-200">
                            {trade.pair}
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant="outline"
                              className={`text-[10px] px-1.5 py-0 ${trade.type === "Buy" ? "text-blue-400 border-blue-400/20 bg-blue-400/10" : "text-orange-400 border-orange-400/20 bg-orange-400/10"}`}
                            >
                              {trade.type}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right text-xs text-zinc-300">
                            {trade.lots.toFixed(2)}
                          </TableCell>
                          <TableCell className="text-right font-mono text-xs text-zinc-300">
                            {trade.open}
                          </TableCell>
                          <TableCell className="text-right font-mono text-xs text-zinc-300">
                            {trade.close}
                          </TableCell>
                          <TableCell
                            className={`text-right font-bold text-xs ${trade.status === "win" ? "text-[#78b30a]" : "text-red-500"}`}
                          >
                            {trade.status === "win" ? "+" : ""}$
                            {trade.pl.toFixed(2)}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-3 mt-3">
        <Card className="bg-[#09090b] border-border/50 rounded-md overflow-hidden relative lg:col-span-3">
          <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-primary/50 to-transparent opacity-50"></div>
          <CardHeader className="pb-2 pt-3 px-4 border-b border-white/5 bg-white/[0.02]">
            <CardTitle className="text-[11px] font-mono text-zinc-400 flex items-center gap-2 uppercase tracking-widest">
              <div className="w-1.5 h-1.5 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.8)]"></div>
              System Logs
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 font-mono text-[11px] h-[160px] overflow-y-auto">
            <div className="space-y-1 text-zinc-400">
              {systemLogs?.length ? systemLogs.map((logStr, i) => {
                return (
                  <div key={i} className="flex gap-3 whitespace-nowrap overflow-hidden text-ellipsis hover:text-zinc-300">
                    <span className="text-zinc-500">{logStr}</span>
                  </div>
                );
              }) : (
                <div className="flex gap-3">
                  <span className="text-zinc-500 w-12 shrink-0">WAIT</span>
                  <span className="text-zinc-500">Waiting for logs...</span>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="bg-[#09090b] border-border/50 rounded-md overflow-hidden relative lg:col-span-1 flex flex-col">
          <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-blue-500/50 to-transparent opacity-50"></div>
          <CardHeader className="pb-2 pt-3 px-4 border-b border-white/5 bg-white/[0.02]">
            <CardTitle className="text-[11px] font-mono text-zinc-400 flex items-center gap-2 uppercase tracking-widest">
              <Activity className="w-3.5 h-3.5 text-blue-400" />
              Agent Brain
            </CardTitle>
          </CardHeader>
          <CardContent className="p-4 flex-1 flex flex-col justify-center">
            {activeSession ? (
              <div className="space-y-4">
                <div className="flex flex-col gap-1 items-center">
                  <span className="text-xs text-muted-foreground uppercase tracking-wider">Current Intent</span>
                  <span className={`text-lg font-black tracking-widest ${actionColor}`}>
                    {agentAction}
                  </span>
                </div>
                
                <div className="space-y-2">
                  <div className="flex justify-between text-[10px] font-mono text-muted-foreground px-1">
                    <span>-1 (SHORT)</span>
                    <span>0</span>
                    <span>+1 (LONG)</span>
                  </div>
                  <div className="h-2 w-full bg-zinc-800 rounded-full overflow-hidden relative">
                    <div 
                      className={`absolute top-0 left-0 h-full rounded-full transition-all duration-300 ${prediction > 0.5 ? 'bg-green-500' : prediction < -0.5 ? 'bg-red-500' : 'bg-zinc-500'}`}
                      style={{ width: `${predictionPercent}%` }}
                    />
                    <div className="absolute top-0 left-1/2 w-px h-full bg-zinc-400/50 -translate-x-1/2"></div>
                    <div className="absolute top-0 left-[25%] w-px h-full bg-red-500/30 -translate-x-1/2"></div>
                    <div className="absolute top-0 left-[75%] w-px h-full bg-green-500/30 -translate-x-1/2"></div>
                  </div>
                  <div className="text-center font-mono text-xs text-zinc-300">
                    Raw Val: {prediction.toFixed(4)}
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center text-muted-foreground gap-2 h-full">
                <BrainCircuit className="w-8 h-8 opacity-20" />
                <span className="text-xs">No active agent</span>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Middle Section: Chart & Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        {/* Chart */}
        <Card className="lg:col-span-2 bg-card rounded-md">
          <CardHeader className="pb-2 pt-3 px-4">
            <CardTitle className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
              Equity Curve
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4">
            <ChartContainer
              config={chartConfig}
              className="min-h-[220px] max-h-[260px] w-full mt-2"
            >
              <AreaChart
                accessibilityLayer
                data={dynamicChartData}
                margin={{ left: -20, right: 12, top: 12, bottom: 0 }}
              >
                <CartesianGrid
                  vertical={false}
                  strokeDasharray="3 3"
                  className="stroke-muted/30"
                />
                <XAxis
                  dataKey="day"
                  tickLine={false}
                  axisLine={false}
                  tickMargin={8}
                  className="text-muted-foreground text-xs"
                />
                <YAxis
                  tickLine={false}
                  axisLine={false}
                  tickMargin={8}
                  domain={["dataMin - 1000", "dataMax + 1000"]}
                  tickFormatter={(value) => `$${value.toLocaleString()}`}
                  className="text-muted-foreground text-xs"
                />
                <ChartTooltip
                  cursor={false}
                  content={<ChartTooltipContent />}
                />
                <defs>
                  <linearGradient id="fillBalance" x1="0" y1="0" x2="0" y2="1">
                    <stop
                      offset="5%"
                      stopColor="var(--color-balance)"
                      stopOpacity={0.3}
                    />
                    <stop
                      offset="95%"
                      stopColor="var(--color-balance)"
                      stopOpacity={0}
                    />
                  </linearGradient>
                </defs>
                <Area
                  dataKey="balance"
                  type="monotone"
                  fill="url(#fillBalance)"
                  fillOpacity={0.4}
                  stroke="var(--color-balance)"
                  strokeWidth={2}
                />
              </AreaChart>
            </ChartContainer>
          </CardContent>
        </Card>

        {/* Trading Statistics */}
        <Card className="bg-card rounded-md">
          <CardHeader className="pb-2 pt-3 px-4">
            <CardTitle className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">
              Trading Statistics
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 px-4 pb-4">
            <div>
              <div className="flex justify-between items-end mb-1.5">
                <span className="text-[11px] font-medium text-muted-foreground uppercase tracking-widest">
                  Win Rate
                </span>
                <span className="text-lg font-bold tabular-nums">68.4%</span>
              </div>
              <Progress value={68.4} className="h-1.5" />
            </div>

            <div className="grid grid-cols-2 gap-y-3 gap-x-4 pt-3 border-t border-border/50">
              <div>
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-0.5">
                  Total Trades
                </p>
                <p className="text-sm font-semibold tabular-nums">142</p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-0.5">
                  Profit Factor
                </p>
                <p className="text-sm font-semibold tabular-nums text-primary">
                  1.82
                </p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-0.5">
                  Average Win
                </p>
                <p className="text-sm font-semibold tabular-nums text-green-500">
                  +$840.50
                </p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-0.5">
                  Average Loss
                </p>
                <p className="text-sm font-semibold tabular-nums text-red-500">
                  -$461.20
                </p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-0.5">
                  Sharpe Ratio
                </p>
                <p className="text-sm font-semibold tabular-nums">1.94</p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-0.5">
                  Sortino Ratio
                </p>
                <p className="text-sm font-semibold tabular-nums">2.31</p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-0.5">
                  Expectancy
                </p>
                <p className="text-sm font-semibold tabular-nums text-green-500">
                  +$124.30
                </p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-0.5">
                  Max Drawdown
                </p>
                <p className="text-sm font-semibold tabular-nums text-orange-500">
                  -2.4%
                </p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-0.5">
                  Consecutive Wins
                </p>
                <p className="text-sm font-semibold tabular-nums">7</p>
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-0.5">
                  Avg Hold Time
                </p>
                <p className="text-sm font-semibold tabular-nums">4h 12m</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
