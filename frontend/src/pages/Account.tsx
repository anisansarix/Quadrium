import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Plus, AlertCircle, Activity, Shield } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { useMt5Account } from "@/api/hooks";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

type ChallengeAccount = {
  id: string;
  type: string;
  phase: string;
  status: string;
  balance: number;
  target: number;
  dailyLossLimit: number;
  currentDailyLoss: number;
  progress: number;
  maxLossLimit: number;
};

export default function Account() {
  const { data: mt5Account, isLoading } = useMt5Account();
  const [createdAccounts, setCreatedAccounts] = useState<ChallengeAccount[]>([]);
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  
  // Form State
  const [accountSize, setAccountSize] = useState("100000");
  const [phases, setPhases] = useState("2");
  const [phase1Goal, setPhase1Goal] = useState("8");
  const [phase2Goal, setPhase2Goal] = useState("5");
  const [dailyLoss, setDailyLoss] = useState("5");
  const [maxLoss, setMaxLoss] = useState("10");

  const handleCreateChallenge = () => {
    const size = parseInt(accountSize);
    const p1Goal = parseFloat(phase1Goal);
    const dLoss = parseFloat(dailyLoss);
    const mLoss = parseFloat(maxLoss);

    const newAccount: ChallengeAccount = {
      id: `CH-${Math.floor(Math.random() * 100000)}`,
      type: `$${size.toLocaleString()} Challenge`,
      phase: phases === "0" ? "Funded" : "Phase 1",
      status: "Active",
      balance: size,
      target: size * (1 + p1Goal / 100),
      dailyLossLimit: size * (dLoss / 100),
      currentDailyLoss: 0,
      progress: 0,
      maxLossLimit: size * (mLoss / 100),
    };

    setCreatedAccounts([...createdAccounts, newAccount]);
    setIsDialogOpen(false);
  };

  return (
    <div className="mx-auto max-w-[1600px] space-y-4">
      <div>
        <h1 className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">My Accounts</h1>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
        
        {/* Render MT5 Live Account */}
        {isLoading ? (
          <Card className="flex flex-col bg-card rounded-md opacity-50 animate-pulse min-h-[220px]" />
        ) : mt5Account ? (
          <Card className="flex flex-col bg-card rounded-md border-primary/20 shadow-[0_0_15px_rgba(120,179,10,0.05)]">
            <CardHeader className="pb-2 pt-3 px-4">
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="text-sm font-bold uppercase tracking-wider flex items-center gap-2">
                    Live MT5 Account
                  </CardTitle>
                  <CardDescription className="font-mono mt-0.5 text-[10px]">Broker: {mt5Account.server}</CardDescription>
                </div>
                <Badge variant="outline" className="text-[10px] py-0 px-2 h-5 rounded-sm text-green-500 border-green-500/30 bg-green-500/10">
                  Connected
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="flex-1 space-y-3 px-4 pb-3">
              
              <div className="flex items-center justify-between text-[11px] font-medium">
                <span className="text-muted-foreground uppercase tracking-widest">Account #</span>
                <span className="font-bold">{mt5Account.login}</span>
              </div>

              <div className="space-y-1.5 pt-1">
                <div className="flex justify-between text-[11px]">
                  <span className="text-muted-foreground uppercase tracking-widest">Balance</span>
                  <span className="font-medium tabular-nums text-sm">${mt5Account.balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                </div>
                <div className="flex justify-between text-[11px]">
                  <span className="text-muted-foreground uppercase tracking-widest">Equity</span>
                  <span className="font-medium tabular-nums text-sm">${mt5Account.equity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 pt-2 mt-auto">
                <div className="flex flex-col bg-muted/40 border border-border/40 p-2 rounded-sm">
                  <span className="text-[10px] text-muted-foreground mb-0.5 flex items-center uppercase tracking-wider"><Shield className="w-2.5 h-2.5 mr-1 text-primary"/> Margin</span>
                  <span className="font-semibold text-xs tabular-nums">${mt5Account.margin_free.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} Free</span>
                </div>
                <div className="flex flex-col bg-muted/40 border border-border/40 p-2 rounded-sm">
                  <span className="text-[10px] text-muted-foreground mb-0.5 flex items-center uppercase tracking-wider"><Activity className="w-2.5 h-2.5 mr-1 text-blue-500"/> Leverage</span>
                  <span className="font-semibold text-xs tabular-nums">1:{mt5Account.leverage}</span>
                </div>
              </div>
            </CardContent>
            <CardFooter className="pt-2 pb-3 px-4 border-t border-border/20">
              <Button size="sm" variant="default" className="w-full rounded-sm h-8 text-[11px] font-bold uppercase tracking-wider bg-[#78b30a] hover:bg-[#659905] text-white">
                Live Trading Active
              </Button>
            </CardFooter>
          </Card>
        ) : null}

        {/* Render New Challenges (Local State) */}
        {createdAccounts.map((acc) => (
          <Card key={acc.id} className="flex flex-col bg-card rounded-md">
            <CardHeader className="pb-2 pt-3 px-4">
              <div className="flex items-start justify-between">
                <div>
                  <CardTitle className="text-sm font-bold uppercase tracking-wider">{acc.type}</CardTitle>
                  <CardDescription className="font-mono mt-0.5 text-[10px]">{acc.id}</CardDescription>
                </div>
                <Badge variant="outline" className="text-[10px] py-0 px-2 h-5 rounded-sm text-blue-500 border-blue-500/30 bg-blue-500/10">
                  {acc.status}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="flex-1 space-y-3 px-4 pb-3">
              <div className="flex items-center justify-between text-[11px] font-medium">
                <span className="text-muted-foreground uppercase tracking-widest">Phase</span>
                <span className="font-bold">{acc.phase}</span>
              </div>
              <div className="space-y-1.5">
                <div className="flex justify-between text-[11px]">
                  <span className="text-muted-foreground uppercase tracking-widest">Target</span>
                  <span className="font-medium tabular-nums">${acc.balance.toLocaleString()} <span className="text-muted-foreground">/ ${acc.target.toLocaleString()}</span></span>
                </div>
                <Progress value={acc.progress} className="h-1.5" />
              </div>
              <div className="grid grid-cols-2 gap-2 pt-2">
                <div className="flex flex-col bg-muted/40 border border-border/40 p-2 rounded-sm">
                  <span className="text-[10px] text-muted-foreground mb-0.5 flex items-center uppercase tracking-wider"><Activity className="w-2.5 h-2.5 mr-1 text-blue-500"/> D. Loss</span>
                  <span className="font-semibold text-xs tabular-nums">${acc.dailyLossLimit.toLocaleString()}</span>
                </div>
                <div className="flex flex-col bg-muted/40 border border-border/40 p-2 rounded-sm">
                  <span className="text-[10px] text-muted-foreground mb-0.5 flex items-center uppercase tracking-wider"><AlertCircle className="w-2.5 h-2.5 mr-1 text-orange-500"/> Drawdown</span>
                  <span className="font-semibold text-xs tabular-nums">${acc.maxLossLimit.toLocaleString()} Max</span>
                </div>
              </div>
            </CardContent>
            <CardFooter className="pt-2 pb-3 px-4 border-t border-border/20">
              <Button size="sm" variant="secondary" className="w-full rounded-sm h-8 text-[11px] font-bold uppercase tracking-wider">
                View Analytics
              </Button>
            </CardFooter>
          </Card>
        ))}

        {/* Start New Challenge Modal */}
        <Card onClick={() => setIsDialogOpen(true)} className="flex flex-col items-center justify-center p-4 border border-dashed border-border/60 hover:bg-muted/10 transition-colors cursor-pointer min-h-[220px] rounded-md shadow-none group">
          <div className="w-10 h-10 rounded-sm bg-muted/40 flex items-center justify-center mb-3">
            <Plus className="w-5 h-5 text-muted-foreground group-hover:text-primary transition-colors" />
          </div>
          <h3 className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground group-hover:text-primary transition-colors">Start New Challenge</h3>
        </Card>

        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogContent className="sm:max-w-[425px] bg-[#18181b] border-white/5 text-zinc-100">
            <DialogHeader>
              <DialogTitle className="text-zinc-100">Create New Account</DialogTitle>
              <DialogDescription className="text-zinc-400 text-xs">
                Configure your prop firm challenge or custom paper trading account.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-xs text-zinc-300">Account Size</Label>
                  <Select value={accountSize} onValueChange={(val) => val && setAccountSize(val)}>
                    <SelectTrigger className="bg-[#27272a] border-white/5 text-zinc-300">
                      <SelectValue placeholder="Size" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="5000">$5,000</SelectItem>
                      <SelectItem value="10000">$10,000</SelectItem>
                      <SelectItem value="25000">$25,000</SelectItem>
                      <SelectItem value="50000">$50,000</SelectItem>
                      <SelectItem value="100000">$100,000</SelectItem>
                      <SelectItem value="200000">$200,000</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label className="text-xs text-zinc-300">Phases</Label>
                  <Select value={phases} onValueChange={(val) => val && setPhases(val)}>
                    <SelectTrigger className="bg-[#27272a] border-white/5 text-zinc-300">
                      <SelectValue placeholder="Phases" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="0">Instant Funding</SelectItem>
                      <SelectItem value="1">1 Phase</SelectItem>
                      <SelectItem value="2">2 Phases</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {phases !== "0" && (
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label className="text-xs text-zinc-300">Phase 1 Goal (%)</Label>
                    <Input 
                      type="number" 
                      value={phase1Goal} 
                      onChange={(e) => setPhase1Goal(e.target.value)} 
                      className="bg-[#27272a] border-white/5 text-zinc-300" 
                    />
                  </div>
                  {phases === "2" && (
                    <div className="space-y-2">
                      <Label className="text-xs text-zinc-300">Phase 2 Goal (%)</Label>
                      <Input 
                        type="number" 
                        value={phase2Goal} 
                        onChange={(e) => setPhase2Goal(e.target.value)} 
                        className="bg-[#27272a] border-white/5 text-zinc-300" 
                      />
                    </div>
                  )}
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-xs text-zinc-300">Daily Loss Limit (%)</Label>
                  <Input 
                    type="number" 
                    value={dailyLoss} 
                    onChange={(e) => setDailyLoss(e.target.value)} 
                    className="bg-[#27272a] border-white/5 text-zinc-300" 
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-xs text-zinc-300">Max Drawdown (%)</Label>
                  <Input 
                    type="number" 
                    value={maxLoss} 
                    onChange={(e) => setMaxLoss(e.target.value)} 
                    className="bg-[#27272a] border-white/5 text-zinc-300" 
                  />
                </div>
              </div>

            </div>
            <DialogFooter>
              <Button variant="outline" className="text-xs bg-transparent border-white/10 text-zinc-300" onClick={() => setIsDialogOpen(false)}>Cancel</Button>
              <Button onClick={handleCreateChallenge} className="text-xs bg-[#78b30a] hover:bg-[#659905] text-white border-0 shadow-none">Create Account</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

      </div>
    </div>
  );
}
