import type { HTMLAttributes, TdHTMLAttributes, ThHTMLAttributes } from "react";
import { cn } from "@/shared/lib/utils";

export function Table({ className, ...props }: HTMLAttributes<HTMLTableElement>) {
  return (
    <div className="scrollbar-thin w-full overflow-x-auto">
      <table className={cn("w-full min-w-[680px] border-collapse text-left text-sm", className)} {...props} />
    </div>
  );
}

export function TableHeader({ className, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
  return <thead className={cn("border-b border-white/10", className)} {...props} />;
}

export function TableBody({ className, ...props }: HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody className={cn("divide-y divide-white/[.06]", className)} {...props} />;
}

export function TableRow({ className, ...props }: HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr
      className={cn("transition-colors hover:bg-white/[.04]", className)}
      {...props}
    />
  );
}

export function TableHead({ className, ...props }: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={cn("px-3 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-slate-500", className)}
      {...props}
    />
  );
}

export function TableCell({ className, ...props }: TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={cn("px-3 py-3 text-slate-300", className)} {...props} />;
}
