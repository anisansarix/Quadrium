import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { PlaySquare } from "lucide-react"
import { Progress } from "@/components/ui/progress"
import { ScrollArea } from "@/components/ui/scroll-area"

export function Training() {
  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Training</h1>
          <p className="text-muted-foreground">Monitor live ML training jobs.</p>
        </div>
        <Button>
          <PlaySquare className="mr-2 h-4 w-4" />
          Start Job
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Active Job Progress</CardTitle>
            <CardDescription>PPO Agent on XAUUSD</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm font-medium">
                <span>Epoch 42 / 100</span>
                <span className="text-muted-foreground">42%</span>
              </div>
              <Progress value={42} className="h-2" />
            </div>
            
            <div className="grid grid-cols-2 gap-4 pt-4 border-t">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Loss</p>
                <p className="text-2xl font-bold">0.142</p>
              </div>
              <div>
                <p className="text-sm font-medium text-muted-foreground">Reward</p>
                <p className="text-2xl font-bold text-primary">+2.45</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Live Logs</CardTitle>
            <CardDescription>Real-time output from trainer.</CardDescription>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[200px] w-full rounded-md border bg-muted p-4">
              <pre className="text-xs font-mono text-muted-foreground">
{`[2026-09-23 11:42:01] Starting epoch 40
[2026-09-23 11:42:05] Batch loss: 0.155
[2026-09-23 11:42:10] Eval reward: +2.1
[2026-09-23 11:42:15] Starting epoch 41
[2026-09-23 11:42:20] Batch loss: 0.148
[2026-09-23 11:42:25] Eval reward: +2.3
[2026-09-23 11:42:30] Starting epoch 42
[2026-09-23 11:42:35] Batch loss: 0.142`}
              </pre>
            </ScrollArea>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

