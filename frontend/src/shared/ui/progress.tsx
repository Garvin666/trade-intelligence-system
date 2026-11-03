import { cn } from "@/shared/lib/utils";

interface ProgressProps {
  value: number;
  tone?: "cyan" | "amber" | "green" | "red";
  className?: string;
}

const toneClass: Record<NonNullable<ProgressProps["tone"]>, string> = {
  cyan: "from-cyan-400 to-cyan-600",
  amber: "from-amber-300 to-amber-500",
  green: "from-emerald-300 to-emerald-500",
  red: "from-red-300 to-red-500",
};

export function Progress({ value, tone = "cyan", className }: ProgressProps) {
  return (
    <div className={cn("glass-inset h-1.5 w-full overflow-hidden", className)}>
      <div
        className={cn(
          "h-full rounded-full bg-gradient-to-r transition-all duration-500",
          toneClass[tone],
        )}
        style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
      />
    </div>
  );
}
