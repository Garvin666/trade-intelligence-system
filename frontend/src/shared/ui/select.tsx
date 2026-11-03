import * as SelectPrimitive from "@radix-ui/react-select";
import { Check, ChevronDown } from "lucide-react";
import type { ComponentProps } from "react";
import { cn } from "@/shared/lib/utils";

export interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps {
  value: string;
  onValueChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  className?: string;
  ariaLabel?: string;
}

export function Select({
  value,
  onValueChange,
  options,
  placeholder = "请选择",
  className,
  ariaLabel,
}: SelectProps) {
  return (
    <SelectPrimitive.Root value={value} onValueChange={onValueChange}>
      <SelectPrimitive.Trigger
        aria-label={ariaLabel}
        className={cn(
          "focus-ring glass-inset flex h-10 w-full items-center justify-between gap-2 px-3 text-sm text-slate-200 data-[placeholder]:text-slate-500",
          className,
        )}
      >
        <SelectPrimitive.Value placeholder={placeholder} />
        <SelectPrimitive.Icon>
          <ChevronDown className="h-4 w-4 text-slate-400" />
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content
          position="popper"
          sideOffset={6}
          className="trade-surface z-50 max-h-72 w-[var(--radix-select-trigger-width)] overflow-hidden p-1 text-slate-200"
        >
          <SelectPrimitive.Viewport>
            {options.map((option) => (
              <SelectPrimitive.Item
                key={option.value}
                value={option.value}
                className="focus-ring relative flex cursor-pointer select-none items-center rounded-lg py-2 pl-8 pr-3 text-sm outline-none data-[highlighted]:bg-accent/10 data-[highlighted]:text-accent"
              >
                <SelectPrimitive.ItemIndicator className="absolute left-2.5">
                  <Check className="h-4 w-4 text-accent" />
                </SelectPrimitive.ItemIndicator>
                <SelectPrimitive.ItemText>{option.label}</SelectPrimitive.ItemText>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
}

export type { ComponentProps };
