import { Outlet } from "react-router-dom";
import { useLocation } from "react-router-dom";
import { cn } from "@/shared/lib/utils";
import { LogoMark } from "@/shared/brand/LogoMark";
import { TopNav } from "./TopNav";
import {
  StarfieldBackground,
  type StarfieldVariant,
} from "@/shared/motion/StarfieldBackground";

const STARFIELD_BY_PATH: Record<string, StarfieldVariant> = {
  "/agent": "agent",
  "/dashboard": "dashboard",
  "/workbench": "workbench",
  "/trade": "trade",
  "/plans": "plans",
  "/system": "system",
  "/about": "about",
};

export function AppShell() {
  const location = useLocation();
  const path = location.pathname.replace(/\/+$/, "") || "/";
  const isConsole = path !== "/";

  return (
    <div className={cn("min-h-screen", isConsole && "trade-console")}>
      {isConsole && <StarfieldBackground variant={STARFIELD_BY_PATH[path] ?? "dashboard"} />}
      <TopNav />
      <main className="relative z-10">
        <Outlet />
      </main>
      {isConsole && (
        <footer className="relative z-10 mt-16 border-t border-white/8 py-6 text-center text-xs text-slate-500">
          <LogoMark size={22} className="mx-auto mb-2" />
          远帆智品 · 贸易决策智能 · 政策到利润的可追溯 Go/No-Go 决策
        </footer>
      )}
    </div>
  );
}
