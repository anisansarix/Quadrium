import { Button } from "@/components/ui/button";
import { Link, Outlet, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  User,
  BrainCircuit,
  Settings,
} from "lucide-react";

export default function Layout() {
  const location = useLocation();

  const navLinks = [
    { name: "Dashboard", path: "/", icon: LayoutDashboard },
    { name: "Account", path: "/account", icon: User },
    { name: "AI/ML", path: "/ai-ml", icon: BrainCircuit },
    { name: "Settings", path: "/settings", icon: Settings },
  ];

  const isActive = (path: string) => {
    if (path === "/") return location.pathname === "/";
    return location.pathname.startsWith(path);
  };

  return (
    <div className="dark bg-background min-h-screen text-foreground font-sans flex flex-col">
      <header className="sticky top-0 z-50 w-full border-b border-border/40 bg-background/95 backdrop-blur-md">
        <div className="flex h-10 items-center px-4 max-w-[1600px] mx-auto w-full justify-between">
          <div className="flex items-center gap-2">
            <span className="font-bold text-sm tracking-widest text-primary uppercase">
              Quadrium
            </span>
          </div>
          <nav className="hidden md:flex items-center gap-1 text-xs font-medium text-muted-foreground uppercase tracking-wider">
            {navLinks.map((link) => {
              const Icon = link.icon;
              return (
                <Link
                  key={link.name}
                  to={link.path}
                  className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-sm transition-colors hover:text-primary hover:bg-muted/50 ${
                    isActive(link.path)
                      ? "text-primary bg-muted/50"
                      : ""
                  }`}
                >
                  <Icon className="w-3 h-3" />
                  {link.name}
                </Link>
              );
            })}
          </nav>
          <div className="flex items-center gap-4">
            <Button
              size="sm"
              className="rounded-sm px-4 text-xs font-bold transition-colors"
            >
              Activate
            </Button>
          </div>
        </div>
      </header>

      <main className="flex-1 p-4">
        <Outlet />
      </main>
    </div>
  );
}
