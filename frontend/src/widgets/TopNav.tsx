import { useState, type ComponentProps, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import {
  Bot,
  BrainCircuit,
  FolderKanban,
  Info,
  LayoutDashboard,
  Menu,
  Rocket,
  ServerCog,
  Ship,
  Wrench,
  X,
} from "lucide-react";
import { cn } from "@/shared/lib/utils";
import { LogoLockup } from "@/shared/brand/LogoLockup";
import { Button } from "@/shared/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTrigger } from "@/shared/ui/dialog";
import { AiConfigPanel } from "@/features/ai-config/AiConfigPanel";
import { useTransitionNavigate } from "./RouteTransition";

const navItems = [
  { to: "/", label: "首页", icon: Rocket },
  { to: "/agent", label: "小助手", icon: Bot },
  { to: "/dashboard", label: "选品看板", icon: LayoutDashboard },
  { to: "/workbench", label: "四脑工作台", icon: BrainCircuit },
  { to: "/trade", label: "贸易决策", icon: Ship },
  { to: "/plans", label: "方案中心", icon: FolderKanban },
  { to: "/system", label: "系统控制台", icon: ServerCog },
  { to: "/about", label: "关于", icon: Info },
];

interface TransitionNavLinkProps extends ComponentProps<typeof NavLink> {
  onNavigate?: () => void;
}

function TransitionNavLink({
  onNavigate,
  children,
  ...props
}: TransitionNavLinkProps) {
  const transitionNavigate = useTransitionNavigate();
  return (
    <NavLink
      {...props}
      onClick={(event) => {
        event.preventDefault();
        onNavigate?.();
        const target = typeof props.to === "string" ? props.to : props.to.pathname;
        transitionNavigate(target || "/");
      }}
    >
      {children as ReactNode}
    </NavLink>
  );
}

export function TopNav() {
  const [open, setOpen] = useState(false);
  const transitionNavigate = useTransitionNavigate();

  return (
    <header className="sticky top-0 z-50 border-b border-white/8 bg-base/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-[1440px] items-center gap-4 px-4 sm:px-6">
        <button
          type="button"
          onClick={() => transitionNavigate("/")}
          className="focus-ring rounded-lg"
          aria-label="返回首页"
        >
          <LogoLockup compact />
        </button>

        <nav className="ml-auto hidden items-center gap-1 lg:flex" aria-label="主导航">
          {navItems.map((item) => (
            <TransitionNavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                cn(
                  "focus-ring flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-slate-400 transition-colors hover:bg-white/10 hover:text-white",
                  isActive && "bg-accent/10 text-accent",
                )
              }
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </TransitionNavLink>
          ))}
        </nav>

        <Dialog>
          <DialogTrigger asChild>
            <Button variant="outline" size="sm" className="ml-auto hidden sm:inline-flex">
              <Wrench className="h-4 w-4" />
              AI 接入
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader
              title="AI 接入"
              description="配置统一模型与搜索参数，配置只保存在当前浏览器会话。"
            />
            <AiConfigPanel />
          </DialogContent>
        </Dialog>

        <button
          type="button"
          className="focus-ring ml-2 rounded-lg border border-white/10 p-2 text-slate-300 hover:bg-white/10 lg:hidden"
          onClick={() => setOpen((value) => !value)}
          aria-expanded={open}
          aria-label="打开导航"
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {open && (
        <nav className="border-t border-white/8 bg-overlay/95 px-4 py-3 lg:hidden" aria-label="移动端导航">
          <div className="grid gap-1">
            {navItems.map((item) => (
              <TransitionNavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                onNavigate={() => setOpen(false)}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 rounded-lg px-3 py-3 text-sm font-medium text-slate-300 hover:bg-white/10",
                    isActive && "bg-accent/10 text-accent",
                  )
                }
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </TransitionNavLink>
            ))}
            <Button
              variant="outline"
              className="mt-2"
              onClick={() => {
                setOpen(false);
                transitionNavigate("/trade");
              }}
            >
              <Wrench className="h-4 w-4" />
              AI 接入
            </Button>
          </div>
        </nav>
      )}
    </header>
  );
}
