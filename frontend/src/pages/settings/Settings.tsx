import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Settings as SettingsIcon } from "lucide-react"

export function Settings() {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p className="text-muted-foreground">System configuration, API keys, and global preferences.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Configuration</CardTitle>
          <CardDescription>Update your local environment setup.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center h-[300px] border border-dashed rounded-md gap-4">
            <SettingsIcon className="h-10 w-10 text-muted-foreground" />
            <div className="text-center">
              <h3 className="text-lg font-medium">Settings Panel</h3>
              <p className="text-sm text-muted-foreground mt-1">Form inputs to be implemented.</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
