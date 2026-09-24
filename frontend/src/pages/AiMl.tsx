import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { Database, LineChart, FlaskConical, Cpu, ShieldAlert, BrainCircuit, BarChart3 } from "lucide-react";

import { Data } from "./data/Data";
import { Datasets } from "./datasets/Datasets";
import { Experiments } from "./experiments/Experiments";
import { Training } from "./training/Training";
import { Risk } from "./risk/Risk";
import { Backtest } from "./backtest/Backtest";

export default function AiMl() {
  return (
    <div className="mx-auto max-w-[1600px] space-y-4">
      <div className="flex items-center gap-2">
        <BrainCircuit className="w-5 h-5 text-primary" />
        <h1 className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground">AI & Machine Learning Lab</h1>
      </div>

      <Tabs defaultValue="market-data" className="w-full">
        <TabsList className="flex overflow-x-auto h-8 w-full justify-start md:grid md:grid-cols-6 gap-1 bg-muted/50 p-1 rounded-sm">
          <TabsTrigger value="market-data" className="flex-1 gap-2 whitespace-nowrap data-[state=active]:bg-background data-[state=active]:shadow-sm text-[10px] uppercase tracking-wider h-6 rounded-sm">
            <LineChart className="w-3 h-3" /> Market Data
          </TabsTrigger>
          <TabsTrigger value="datasets" className="flex-1 gap-2 whitespace-nowrap data-[state=active]:bg-background data-[state=active]:shadow-sm text-[10px] uppercase tracking-wider h-6 rounded-sm">
            <Database className="w-3 h-3" /> Datasets
          </TabsTrigger>
          <TabsTrigger value="experiments" className="flex-1 gap-2 whitespace-nowrap data-[state=active]:bg-background data-[state=active]:shadow-sm text-[10px] uppercase tracking-wider h-6 rounded-sm">
            <FlaskConical className="w-3 h-3" /> Experiments
          </TabsTrigger>
          <TabsTrigger value="training" className="flex-1 gap-2 whitespace-nowrap data-[state=active]:bg-background data-[state=active]:shadow-sm text-[10px] uppercase tracking-wider h-6 rounded-sm">
            <Cpu className="w-3 h-3" /> Training
          </TabsTrigger>
          <TabsTrigger value="backtest" className="flex-1 gap-2 whitespace-nowrap data-[state=active]:bg-background data-[state=active]:shadow-sm text-[10px] uppercase tracking-wider h-6 rounded-sm">
            <BarChart3 className="w-3 h-3" /> Backtest
          </TabsTrigger>
          <TabsTrigger value="risk-analysis" className="flex-1 gap-2 whitespace-nowrap data-[state=active]:bg-background data-[state=active]:shadow-sm text-[10px] uppercase tracking-wider h-6 rounded-sm">
            <ShieldAlert className="w-3 h-3" /> Risk Analysis
          </TabsTrigger>
        </TabsList>
        
        <div className="mt-3">
          <TabsContent value="market-data" className="m-0">
            <Data />
          </TabsContent>

          <TabsContent value="datasets" className="m-0">
            <Datasets />
          </TabsContent>

          <TabsContent value="experiments" className="m-0">
            <Experiments />
          </TabsContent>

          <TabsContent value="training" className="m-0">
            <Training />
          </TabsContent>
          
          <TabsContent value="backtest" className="m-0">
            <Backtest />
          </TabsContent>

          <TabsContent value="risk-analysis" className="m-0">
            <Risk />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
