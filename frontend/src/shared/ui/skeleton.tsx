import { cn } from "@/shared/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "animate-pulse rounded-lg bg-white/[.07]",
        className,
      )}
      aria-hidden="true"
    />
  );
}
