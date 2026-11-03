import { useState } from "react";
import { Download } from "lucide-react";
import { fetchTradeReport } from "@/shared/api/client";
import { useTradeReport } from "@/shared/api/hooks";
import { IS_OFFLINE } from "@/shared/api/offline";
import { marketName } from "@/shared/lib/names";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { GlassCard } from "@/shared/ui/glass-card";
import { Select } from "@/shared/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/ui/table";

const marketOptions = [
  "us", "eu", "sea", "jp", "ca", "au", "uk", "kr", "de", "fr", "vn", "ru", "hu", "ae", "mx",
].map((value) => ({ value, label: marketName(value) }));

export function TradeReportPanel() {
  const [market, setMarket] = useState("");
  const [risk, setRisk] = useState("");
  const { data, isLoading, isError } = useTradeReport({
    market: market || undefined,
    risk_level: risk || undefined,
  });
  const rows = (data?.rows ?? []) as Record<string, unknown>[];

  if (IS_OFFLINE) {
    return (
      <GlassCard>
        <p className="text-sm text-slate-400">贸易演示报告需要在线后端，离线模式不可用。</p>
      </GlassCard>
    );
  }

  if (isLoading && !data) {
    return <div className="glass h-64 animate-pulse" />;
  }

  if (isError || !data) {
    return (
      <GlassCard>
        <p className="text-sm text-red-300">贸易报告加载失败。</p>
      </GlassCard>
    );
  }

  const summary = (data.summary ?? {}) as Record<string, unknown>;

  const exportCsv = async () => {
    const full = await fetchTradeReport({
      market: market || undefined,
      risk_level: risk || undefined,
    });
    const exportRows = (full.rows ?? []) as Record<string, unknown>[];
    if (!exportRows.length) return;
    const headers = [
      "category_name",
      "market_name",
      "risk_level",
      "effective_tariff_rate",
      "duty_usd_per_unit",
      "margin_pct",
      "best_logistics",
      "financing_level",
      "conflict_level",
    ];
    const lines = [
      headers.join(","),
      ...exportRows.map((row) =>
        headers
          .map((header) => String(row[header] ?? "").replaceAll(",", " "))
          .join(","),
      ),
    ];
    const blob = new Blob(["\uFEFF" + lines.join("\n")], {
      type: "text/csv;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "trade_demo_report.csv";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <GlassCard title="贸易演示报告" description={String(data.generated_at ?? "最近一次生成")} strong>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="组合数" value={String(summary.combos ?? "--")} />
        <Stat label="高风险" value={String(summary.high_risk ?? "--")} />
        <Stat label="平均利润率" value={summary.avg_margin_pct != null ? `${summary.avg_margin_pct}%` : "--"} />
        <Stat label="过滤后行数" value={String(data.filtered ?? rows.length)} />
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Select
          value={market}
          onValueChange={setMarket}
          options={[{ value: "", label: "全部市场" }, ...marketOptions]}
          className="w-44"
          ariaLabel="筛选市场"
        />
        <Select
          value={risk}
          onValueChange={setRisk}
          options={[
            { value: "", label: "全部风险" },
            { value: "high", label: "高风险" },
            { value: "medium", label: "中风险" },
            { value: "low", label: "低风险" },
          ]}
          className="w-36"
          ariaLabel="筛选风险"
        />
        <Button variant="secondary" size="sm" onClick={exportCsv} disabled={!rows.length}>
          <Download className="h-3.5 w-3.5" />
          导出 CSV
        </Button>
        <Badge tone="cyan">{rows.length} 行</Badge>
      </div>

      <div className="mt-4 max-h-[480px] overflow-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>品类</TableHead>
              <TableHead>市场</TableHead>
              <TableHead>风险</TableHead>
              <TableHead>利润率</TableHead>
              <TableHead>物流</TableHead>
              <TableHead>融资</TableHead>
              <TableHead>裁决</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.slice(0, 50).map((row, index) => (
              <TableRow key={index}>
                <TableCell className="font-semibold text-white">{String(row.category_name ?? "--")}</TableCell>
                <TableCell>{String(row.market_name ?? "--")}</TableCell>
                <TableCell>
                  <Badge tone={row.risk_level === "high" ? "red" : row.risk_level === "medium" ? "amber" : "green"}>
                    {String(row.risk_level ?? "--")}
                  </Badge>
                </TableCell>
                <TableCell className="tabular">{row.margin_pct != null ? `${row.margin_pct}%` : "--"}</TableCell>
                <TableCell>{String(row.best_logistics ?? "--")}</TableCell>
                <TableCell>{String(row.financing_level ?? "--")}</TableCell>
                <TableCell>{String(row.conflict_level ?? "--")}</TableCell>
              </TableRow>
            ))}
            {!rows.length && (
              <TableRow>
                <TableCell colSpan={7} className="text-center text-slate-500">暂无匹配行</TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </GlassCard>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="glass-inset p-3">
      <p className="text-[11px] font-semibold text-slate-500">{label}</p>
      <p className="tabular mt-1 text-lg font-extrabold text-white">{value}</p>
    </div>
  );
}
