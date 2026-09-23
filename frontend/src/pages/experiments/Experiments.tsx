import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Activity, Plus, MoreHorizontal } from "lucide-react"
import { useExperiments } from "@/api/hooks"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Badge } from "@/components/ui/badge"

export function Experiments() {
  const { data: experiments, isLoading } = useExperiments()

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Experiments</h1>
          <p className="text-muted-foreground">Manage and compare RL models.</p>
        </div>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          New Experiment
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Experiment Tracking</CardTitle>
          <CardDescription>Track hyperparameters, metrics, and models.</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex justify-center items-center h-32">
              <span className="text-muted-foreground">Loading...</span>
            </div>
          ) : !experiments || experiments.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-[400px] border border-dashed rounded-md gap-4">
              <Activity className="h-10 w-10 text-muted-foreground" />
              <div className="text-center">
                <h3 className="text-lg font-medium">No experiments found</h3>
                <p className="text-sm text-muted-foreground mt-1">Start your first training experiment.</p>
              </div>
              <Button variant="outline" className="mt-2">
                <Plus className="mr-2 h-4 w-4" />
                New Experiment
              </Button>
            </div>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Instrument</TableHead>
                    <TableHead>Timeframe</TableHead>
                    <TableHead>Agent</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {experiments.map((exp) => (
                    <TableRow key={exp.id}>
                      <TableCell className="font-medium text-primary">{exp.name}</TableCell>
                      <TableCell>
                        <Badge variant={exp.status === 'completed' ? 'default' : exp.status === 'failed' ? 'destructive' : 'secondary'}>
                          {exp.status}
                        </Badge>
                      </TableCell>
                      <TableCell>{exp.instrument}</TableCell>
                      <TableCell>{exp.timeframe}</TableCell>
                      <TableCell>
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-muted text-muted-foreground">
                          {exp.agent_type}
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" className="h-8 w-8 p-0">
                              <span className="sr-only">Open menu</span>
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuLabel>Actions</DropdownMenuLabel>
                            <DropdownMenuItem>View Details</DropdownMenuItem>
                            <DropdownMenuItem>View Logs</DropdownMenuItem>
                            <DropdownMenuSeparator />
                            <DropdownMenuItem className="text-destructive">Delete</DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
