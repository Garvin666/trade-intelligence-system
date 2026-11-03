import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/shared/lib/utils";

const buttonVariants = cva(
  "focus-ring inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg font-semibold transition-all duration-200 active:scale-[.98] disabled:pointer-events-none disabled:opacity-45",
  {
    variants: {
      variant: {
        primary:
          "border border-accent/40 bg-gradient-to-r from-accent to-cyan-600 text-white shadow-[0_10px_28px_-12px_rgba(34,211,238,.5)] [text-shadow:0_1px_14px_rgba(165,243,252,.45)] hover:brightness-110",
        secondary:
          "glass-soft text-slate-100 hover:bg-white/10 hover:border-white/20",
        ghost: "text-slate-300 hover:bg-white/10 hover:text-white",
        outline:
          "border border-accent/30 bg-transparent text-accent hover:bg-accent/10",
        danger:
          "border border-red-400/30 bg-red-500/15 text-red-200 hover:bg-red-500/25",
      },
      size: {
        default: "h-10 px-4 text-sm",
        sm: "h-8 px-3 text-xs",
        lg: "h-11 px-5 text-sm",
        icon: "h-10 w-10 p-0",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, type = "button", ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  ),
);
Button.displayName = "Button";
