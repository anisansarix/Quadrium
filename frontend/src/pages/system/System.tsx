import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Server } from "lucide-react"

export function System() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">System Status</h1>
        <p className="text-muted-foreground">Monitor hardware, services, and backend health.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Hardware Monitor</CardTitle>
            <CardDescription>CPU, Memory, and GPU usage.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col items-center justify-center h-[200px] border border-dashed rounded-md gap-4">
              <Server className="h-10 w-10 text-muted-foreground" />
              <div className="text-center">
                <h3 className="text-lg font-medium">Monitoring active</h3>
                <p className="text-sm text-muted-foreground mt-1">RTX 3050 VRAM: 1.2 / 4 GB</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Services</CardTitle>
            <CardDescription>Backend API and Database connections.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between p-3 border rounded-md">
                <span className="font-medium">FastAPI Backend</span>
                <span className="text-emerald-500 text-sm font-bold">Online</span>
              </div>
              <div className="flex items-center justify-between p-3 border rounded-md">
                <span className="font-medium">DuckDB (Analytics)</span>
                <span className="text-emerald-500 text-sm font-bold">Connected</span>
              </div>
              <div className="flex items-center justify-between p-3 border rounded-md">
                <span className="font-medium">SQLite (State)</span>
                <span className="text-emerald-500 text-sm font-bold">Connected</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
