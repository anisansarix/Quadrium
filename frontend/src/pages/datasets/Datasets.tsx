import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { FileCode, Plus, HardDrive } from "lucide-react"
import { useDatasets } from "@/api/hooks"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

export function Datasets() {
  const { data: datasets, isLoading } = useDatasets()

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Datasets</h1>
          <p className="text-muted-foreground">Processed datasets with feature engineering applied.</p>
        </div>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          Create Dataset
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Dataset Catalog</CardTitle>
          <CardDescription>Ready-to-use datasets for model training.</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex justify-center items-center h-32">
              <span className="text-muted-foreground">Loading...</span>
            </div>
          ) : !datasets || datasets.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-[400px] border border-dashed rounded-md gap-4">
              <FileCode className="h-10 w-10 text-muted-foreground" />
              <div className="text-center">
                <h3 className="text-lg font-medium">No datasets found</h3>
                <p className="text-sm text-muted-foreground mt-1">Create a dataset from raw market data.</p>
              </div>
              <Button variant="outline" className="mt-2">
                <Plus className="mr-2 h-4 w-4" />
                Create Dataset
              </Button>
            </div>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Instrument</TableHead>
                    <TableHead>Version</TableHead>
                    <TableHead>Timeframe</TableHead>
                    <TableHead>Date Range</TableHead>
                    <TableHead>Features</TableHead>
                    <TableHead className="text-right">Rows</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {datasets.map((ds) => (
                    <TableRow key={ds.id}>
                      <TableCell className="font-medium">{ds.instrument}</TableCell>
                      <TableCell>
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-primary/10 text-primary border border-primary/20">
                          {ds.version}
                        </span>
                      </TableCell>
                      <TableCell>{ds.timeframe}</TableCell>
                      <TableCell className="text-muted-foreground text-xs">
                        {ds.date_start.split('T')[0]} - {ds.date_end.split('T')[0]}
                      </TableCell>
                      <TableCell>
                        <span className="text-xs text-muted-foreground">
                          {ds.features.length} features
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        {ds.row_count.toLocaleString()}
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
