import { cn } from "@/shared/lib/utils";
import { LogoMark } from "./LogoMark";

interface LogoLockupProps {
  className?: string;
  compact?: boolean;
}

export function LogoLockup({ className, compact = false }: LogoLockupProps) {
  return (
    <div className={cn("flex items-center gap-3 min-w-0", className)}>
      <LogoMark size={compact ? 30 : 38} />
      <div className="min-w-0 leading-tight">
        <div className="truncate text-[15px] font-bold text-white">远帆智品</div>
        <div className="truncate font-mono text-[11px] tracking-[0.12em] text-slate-400 uppercase">
          贸易决策智能 · Trade Intelligence
        </div>
      </div>
    </div>
  );
}
