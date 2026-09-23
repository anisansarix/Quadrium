import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import {
  BarChart2,
  Database,
  LayoutDashboard,
  LineChart,
  Settings,
  Activity,
  PlaySquare,
  ShieldAlert,
  Server
} from "lucide-react"
import { Link, useLocation } from "react-router-dom"

const navItems = [
  { title: "Dashboard", icon: LayoutDashboard, url: "/" },
  { title: "Market Data", icon: Database, url: "/data" },
  { title: "Datasets", icon: Database, url: "/datasets" },
  { title: "Experiments", icon: Activity, url: "/experiments" },
  { title: "Training", icon: PlaySquare, url: "/training" },
  { title: "Backtesting", icon: LineChart, url: "/backtest" },
  { title: "Risk Analysis", icon: ShieldAlert, url: "/risk" },
  { title: "Prop-Firm Sim", icon: BarChart2, url: "/prop-sim" },
]

const systemItems = [
  { title: "Settings", icon: Settings, url: "/settings" },
  { title: "System Status", icon: Server, url: "/system" },
]

export function AppSidebar() {
  const location = useLocation()

  return (
    <Sidebar>
      <SidebarHeader className="h-16 flex items-center px-6 border-b">
        <h2 className="text-lg font-bold">Quadrium</h2>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Research</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton isActive={location.pathname === item.url} render={<Link to={item.url} />}>
                      <item.icon />
                      <span>{item.title}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarGroup>
          <SidebarGroupLabel>System</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {systemItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton isActive={location.pathname === item.url} render={<Link to={item.url} />}>
                      <item.icon />
                      <span>{item.title}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  )
}
