import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { LogoMark } from "@/shared/brand/LogoMark";

interface AgentPageShellProps {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
}

export function AgentPageShell({
  icon: Icon,
  title,
  description,
  action,
  children,
}: AgentPageShellProps) {
  return (
    <div className="relative min-h-[calc(100vh-120px)]">
      <div className="relative z-10 mx-auto max-w-[1280px] px-4 pb-10 pt-8 sm:px-6">
        <header className="mb-7">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div className="min-w-0">
              <p className="star-eyebrow">Trade Intelligence</p>
              <div className="mt-4 flex items-start gap-4">
                <span className="star-page-mark" aria-hidden>
                  <Icon className="h-5 w-5" />
                </span>
                <div className="min-w-0">
                  <h1 className="star-page-title">{title}</h1>
                  {description && (
                    <p className="mt-1.5 max-w-3xl text-sm leading-6 text-slate-400">
                      {description}
                    </p>
                  )}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              {action}
              <LogoMark size={44} className="opacity-90" />
            </div>
          </div>
        </header>
        {children}
      </div>
    </div>
  );
}
