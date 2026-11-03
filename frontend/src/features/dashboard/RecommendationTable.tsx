import {
  ArrowDownRight,
  ArrowUpRight,
  BrainCircuit,
  Crosshair,
  Eye,
  ShieldAlert,
  ShieldCheck,
  Ship,
  Star,
} from "lucide-react";
import type { Recommendation } from "@/shared/api/types";
import { cn } from "@/shared/lib/utils";
import { categoryName, marketName } from "@/shared/lib/names";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/ui/table";

function verdictTone(verdict: string) {
  const key = verdict.toLowerCase();
  if (key.includes("go")) return "green" as const;
  if (key.includes("conditional")) return "amber" as const;
  return "red" as const;
}

export function RecommendationTable({
  rows,
  onOpenDetail,
  onFourBrain,
  onTrade,
  onWatch,
  watchedIds = [],
  onShowNoGo,
  emptyHint,
}: {
  rows: Recommendation[];
  onOpenDetail?: (row: Recommendation) => void;
  onFourBrain?: (row: Recommendation) => void;
  onTrade?: (row: Recommendation) => void;
  onWatch?: (row: Recommendation) => void;
  watchedIds?: string[];
  onShowNoGo?: () => void;
  emptyHint?: string;
}) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="text-right">排名</TableHead>
          <TableHead>组合</TableHead>
          <TableHead className="text-right">六维评分</TableHead>
          <TableHead>判定</TableHead>
          <TableHead className="text-right">增长</TableHead>
          <TableHead className="text-right">趋势</TableHead>
          <TableHead className="text-right">竞争</TableHead>
          <TableHead className="text-right">证据</TableHead>
          <TableHead>操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.length === 0 ? (
          <TableRow>
            <TableCell colSpan={9}>
              <div className="flex flex-col items-center gap-2 py-10 text-center">
                <ShieldAlert className="h-9 w-9 text-amber-300/70" />
                <p className="text-sm font-semibold text-slate-200">当前组合暂无推荐结果</p>
                <p className="max-w-md text-xs leading-5 text-slate-500">
                  {emptyHint ??
                    "该组合可能被判定为 No-Go（不推荐进入），或被证据闸拦截。可查看 No-Go 判定原因，或前往贸易决策查看详情。"}
                </p>
                {onShowNoGo && (
                  <Button size="sm" variant="outline" className="mt-1" onClick={onShowNoGo}>
                    <Eye className="h-3.5 w-3.5" />
                    查看 No-Go 判定原因
                  </Button>
                )}
              </div>
            </TableCell>
          </TableRow>
        ) : (
          rows.map((row) => (
          <TableRow key={`${row.rank}-${row.category}-${row.market}`}>
            <TableCell className="font-mono text-right text-slate-400">#{row.rank}</TableCell>
            <TableCell>
              <div className="font-semibold text-white">
                {categoryName(row.category)} × {marketName(row.market)}
              </div>
              <div className="mt-0.5 flex items-center gap-1 text-[11px] text-slate-500">
                <Crosshair className="h-3 w-3" />
                {row.six_dimension_score.toFixed(1)} / 100
              </div>
              {row.verdict.toLowerCase().includes("no") && row.decision_reason && (
                <div
                  className="mt-1 max-w-[280px] truncate text-[11px] text-red-300/80"
                  title={row.decision_reason}
                >
                  原因：{row.decision_reason}
                </div>
              )}
            </TableCell>
            <TableCell className="text-right">
              <div className="tabular text-sm font-bold text-accent">
                {row.six_dimension_score.toFixed(1)}
              </div>
            </TableCell>
            <TableCell>
              <Badge tone={verdictTone(row.verdict)}>{row.verdict}</Badge>
            </TableCell>
            <TableCell className="text-right">
              <MetricCell value={row.forecast_growth} positiveUp />
            </TableCell>
            <TableCell className="text-right">
              <MetricCell value={row.search_trend} positiveUp />
            </TableCell>
            <TableCell className="text-right">
              <MetricCell value={row.competition} positiveUp={false} />
            </TableCell>
            <TableCell className="text-right">
              <span
                className={cn(
                  "tabular text-sm",
                  row.dimension_evidence >= 40 ? "text-emerald-300" : "text-amber-300",
                )}
              >
                {row.dimension_evidence.toFixed(0)}
              </span>
            </TableCell>
            <TableCell>
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="查看推荐详情"
                  onClick={() => onOpenDetail?.(row)}
                >
                  <Crosshair className="h-3.5 w-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="四脑立项"
                  onClick={() => onFourBrain?.(row)}
                >
                  <BrainCircuit className="h-3.5 w-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="贸易决策"
                  onClick={() => onTrade?.(row)}
                >
                  <Ship className="h-3.5 w-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={watchedIds.includes(`${row.category}-${row.market}`) ? "已关注" : "加入关注"}
                  onClick={() => onWatch?.(row)}
                >
                  <Star
                    className={cn(
                      "h-3.5 w-3.5",
                      watchedIds.includes(`${row.category}-${row.market}`)
                        ? "fill-amber-300 text-amber-300"
                        : "text-slate-400",
                    )}
                  />
                </Button>
              </div>
            </TableCell>
          </TableRow>
          ))
        )}
      </TableBody>
    </Table>
  );
}

function MetricCell({
  value,
  positiveUp,
}: {
  value: number;
  positiveUp: boolean;
}) {
  const good = positiveUp ? value >= 0 : value <= 40;
  return (
    <span
      className={cn(
        "tabular inline-flex items-center gap-1 text-sm",
        good ? "text-emerald-300" : "text-slate-400",
      )}
    >
      {positiveUp ? (
        <ArrowUpRight className="h-3.5 w-3.5" />
      ) : (
        <ArrowDownRight className="h-3.5 w-3.5" />
      )}
      {value.toFixed(1)}
    </span>
  );
}

export function EvidenceIcon() {
  return <ShieldCheck className="h-4 w-4" />;
}
