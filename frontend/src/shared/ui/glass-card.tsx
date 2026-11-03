import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/shared/lib/utils";

interface GlassCardProps extends Omit<HTMLAttributes<HTMLDivElement>, "title"> {
  title?: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  strong?: boolean;
}

export function GlassCard({
  title,
  description,
  action,
  strong = false,
  className,
  children,
  ...props
}: GlassCardProps) {
  return (
    <section
      className={cn(strong ? "glass-strong" : "glass", "p-5", className)}
      {...props}
    >
      {(title || action) && (
        <header className="mb-4 flex items-start justify-between gap-3">
          <div className="min-w-0">
            {title && (
              <h2 className="truncate text-sm font-bold text-white">{title}</h2>
            )}
            {description && (
              <p className="mt-1 text-xs leading-5 text-slate-400">{description}</p>
            )}
          </div>
          {action && <div className="min-w-0 max-w-full">{action}</div>}
        </header>
      )}
      {children}
    </section>
  );
}
