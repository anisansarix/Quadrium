import { BrowserRouter, Routes, Route } from "react-router-dom"
import { Shell } from "./components/layout/Shell"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { Dashboard } from "./pages/dashboard/Dashboard"
import { Data } from "./pages/data/Data"
import { Datasets } from "./pages/datasets/Datasets"
import { Experiments } from "./pages/experiments/Experiments"
import { Training } from "./pages/training/Training"
import { Backtest } from "./pages/backtest/Backtest"
import { Risk } from "./pages/risk/Risk"
import { PropSim } from "./pages/prop-sim/PropSim"
import { Settings } from "./pages/settings/Settings"
import { System } from "./pages/system/System"

const queryClient = new QueryClient()

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Shell />}>
            <Route index element={<Dashboard />} />
            <Route path="data" element={<Data />} />
            <Route path="datasets" element={<Datasets />} />
            <Route path="experiments" element={<Experiments />} />
            <Route path="training" element={<Training />} />
            <Route path="backtest" element={<Backtest />} />
            <Route path="risk" element={<Risk />} />
            <Route path="prop-sim" element={<PropSim />} />
            <Route path="settings" element={<Settings />} />
            <Route path="system" element={<System />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
