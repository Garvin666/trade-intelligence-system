import * as TabsPrimitive from "@radix-ui/react-tabs";
import type { ComponentProps, ReactNode } from "react";
import { cn } from "@/shared/lib/utils";

export const Tabs = TabsPrimitive.Root;

export function TabsList({
  className,
  children,
  ...props
}: ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn(
        "glass-inset inline-flex items-center gap-1 p-1",
        className,
      )}
      {...props}
    >
      {children}
    </TabsPrimitive.List>
  );
}

export function TabsTrigger({
  className,
  children,
  ...props
}: ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        "focus-ring rounded-md px-3 py-1.5 text-xs font-semibold text-slate-400 transition-colors data-[state=active]:bg-accent/15 data-[state=active]:text-accent",
        className,
      )}
      {...props}
    >
      {children}
    </TabsPrimitive.Trigger>
  );
}

export function TabsContent({
  className,
  children,
  ...props
}: ComponentProps<typeof TabsPrimitive.Content>) {
  return (
    <TabsPrimitive.Content className={cn("outline-none", className)} {...props}>
      {children as ReactNode}
    </TabsPrimitive.Content>
  );
}
