import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/shared/lib/utils";

interface KpiValueProps extends HTMLAttributes<HTMLParagraphElement> {
  value: string | number;
}

/** 统一 KPI 数值：display 字号 + 等宽数字 */
export function KpiValue({ value, className, ...props }: KpiValueProps) {
  return (
    <p
      className={cn("tabular text-2xl font-extrabold text-white", className)}
      {...props}
    >
      {value}
    </p>
  );
}

interface ValueCellProps extends HTMLAttributes<HTMLTableCellElement> {
  children: ReactNode;
}

/** 统一数据单元格：右对齐 + 等宽数字，用于表格数字列 */
export function ValueCell({ children, className, ...props }: ValueCellProps) {
  return (
    <td
      className={cn(
        "tabular px-3 py-3 text-right text-sm text-slate-300",
        className,
      )}
      {...props}
    >
      {children}
    </td>
  );
}
