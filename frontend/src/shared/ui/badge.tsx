import type { HTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/shared/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold",
  {
    variants: {
      tone: {
        cyan: "border-accent/30 bg-accent/10 text-cyan-100",
        amber: "border-decision/30 bg-decision/10 text-amber-200",
        green: "border-ok/30 bg-ok/10 text-emerald-200",
        red: "border-danger/30 bg-danger/10 text-red-200",
        neutral: "border-white/10 bg-white/5 text-slate-300",
      },
    },
    defaultVariants: {
      tone: "neutral",
    },
  },
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}
