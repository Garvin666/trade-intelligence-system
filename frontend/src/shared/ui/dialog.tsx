import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";
import { cn } from "@/shared/lib/utils";

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

export function DialogContent({
  className,
  children,
  ...props
}: ComponentProps<typeof DialogPrimitive.Content>) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm" />
      <DialogPrimitive.Content
        className={cn(
          "trade-surface fixed left-1/2 top-1/2 z-50 w-[calc(100vw-32px)] max-w-lg -translate-x-1/2 -translate-y-1/2 p-5 focus:outline-none",
          className,
        )}
        {...props}
      >
        {children}
        <DialogPrimitive.Close
          className="focus-ring absolute right-3 top-3 rounded-lg p-1.5 text-slate-400 hover:bg-white/10 hover:text-white"
          aria-label="关闭"
        >
          <X className="h-4 w-4" />
        </DialogPrimitive.Close>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}

export function DialogHeader({
  title,
  description,
}: {
  title: ReactNode;
  description?: ReactNode;
}) {
  return (
    <header className="mb-4 pr-8">
      <h2 className="text-lg font-bold text-white">{title}</h2>
      {description && <p className="mt-1 text-sm text-slate-400">{description}</p>}
    </header>
  );
}
