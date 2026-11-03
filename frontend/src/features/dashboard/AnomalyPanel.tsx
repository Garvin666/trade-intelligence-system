import { TriangleAlert } from "lucide-react";
import { useAnomalies } from "@/shared/api/hooks";
import { IS_OFFLINE } from "@/shared/api/offline";
import { categoryName, marketName } from "@/shared/lib/names";
import { Badge } from "@/shared/ui/badge";
import { GlassCard } from "@/shared/ui/glass-card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/ui/table";

export function AnomalyPanel() {
  const { data, isLoading } = useAnomalies();

  if (IS_OFFLINE) {
    return (
      <GlassCard title="异常监测" description="离线模式不提供实时异常快照">
        <p className="text-sm text-slate-400">请在线启动后端后查看异常组合。</p>
      </GlassCard>
    );
  }

  const rows = data?.rows ?? [];
  return (
    <GlassCard
      title="异常监测"
      description={data?.generated_at ? `最近更新 ${data.generated_at}` : "销量 / 价格序列异常"}
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Badge tone={rows.length ? "amber" : "green"}>
          <TriangleAlert className="h-3.5 w-3.5" />
          {isLoading ? "加载中" : `${rows.length} 条异常`}
        </Badge>
        {data?.method && (
          <Badge tone="neutral">{String(data.method)}</Badge>
        )}
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>组合</TableHead>
            <TableHead>指标</TableHead>
            <TableHead>日期</TableHead>
            <TableHead>数值</TableHead>
            <TableHead>异常分</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.slice(0, 12).map((row, index) => (
            <TableRow key={`${row.category}-${row.market}-${row.column}-${index}`}>
              <TableCell className="font-semibold text-white">
                {categoryName(String(row.category ?? ""))} ×{" "}
                {marketName(String(row.market ?? ""))}
              </TableCell>
              <TableCell>{String(row.column ?? "--")}</TableCell>
              <TableCell className="font-mono text-xs">{String(row.date ?? "--")}</TableCell>
              <TableCell className="tabular">{num(row.value)}</TableCell>
              <TableCell className="tabular text-amber-200">{num(row.score)}</TableCell>
            </TableRow>
          ))}
          {!rows.length && (
            <TableRow>
              <TableCell colSpan={5} className="text-center text-slate-500">
                暂无异常
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
    </GlassCard>
  );
}

function num(value: unknown): string {
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(2);
  return String(value ?? "--");
}
