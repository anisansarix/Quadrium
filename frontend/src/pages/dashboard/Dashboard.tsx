import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Activity, Server, Database, PlaySquare } from "lucide-react"
import { useSystemHealth, useDatasets, useTrainingJobs } from "@/api/hooks"

export function Dashboard() {
  const { data: health, isLoading: healthLoading } = useSystemHealth()
  const { data: datasets, isLoading: datasetsLoading } = useDatasets()
  const { data: jobs, isLoading: jobsLoading } = useTrainingJobs()

  const activeJobs = jobs?.filter(j => j.status === 'running') || []

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">System overview and recent activity.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Experiments</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {jobsLoading ? "..." : (jobs?.length || 0)}
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Jobs</CardTitle>
            <PlaySquare className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {jobsLoading ? "..." : activeJobs.length}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Datasets</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {datasetsLoading ? "..." : (datasets?.length || 0)}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">System Health</CardTitle>
            <Server className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-primary">
              {healthLoading ? "..." : (health?.status === 'ok' ? 'Online' : 'Offline')}
            </div>
            <p className="text-xs text-muted-foreground">
              {health?.gpu_available ? `GPU: ${health.gpu_name}` : 'No GPU'}
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
        <Card className="lg:col-span-4">
          <CardHeader>
            <CardTitle>Recent Experiments</CardTitle>
            <CardDescription>Latest models trained and backtested.</CardDescription>
          </CardHeader>
          <CardContent>
            {/* Table placeholder */}
            <div className="h-[300px] flex items-center justify-center border border-dashed rounded-md text-muted-foreground">
              No recent experiments.
            </div>
          </CardContent>
        </Card>
        
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle>System Logs</CardTitle>
            <CardDescription>Recent backend activity.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[300px] flex items-center justify-center border border-dashed rounded-md text-muted-foreground text-sm">
              <pre className="p-4 rounded-md bg-secondary text-secondary-foreground w-full h-full overflow-auto">
                {JSON.stringify(health, null, 2)}
              </pre>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
