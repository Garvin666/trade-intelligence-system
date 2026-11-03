import { useMemo, useState } from "react";
import { SearchCode } from "lucide-react";
import { useHsCodesSearch, useTradeCatalog } from "@/shared/api/hooks";
import { IS_OFFLINE } from "@/shared/api/offline";
import {
  categoryName,
  fallbackCategoryOptions,
  marketName,
} from "@/shared/lib/names";
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

export function HsCodePanel() {
  const { data: catalog } = useTradeCatalog();
  const categoryOptions = useMemo(() => {
    const items = catalog?.data?.categories ?? [];
    if (items.length) {
      return items
        .filter((item) => item.key)
        .map((item) => ({ value: item.key, label: String(item.label ?? categoryName(item.key)) }));
    }
    return fallbackCategoryOptions;
  }, [catalog]);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [market, setMarket] = useState("");
  const [enabled, setEnabled] = useState(false);
  const { data, isLoading } = useHsCodesSearch({ q: query, category, market }, enabled);

  if (IS_OFFLINE) {
    return (
      <GlassCard>
        <p className="text-sm text-slate-400">HS Code 检索需要在线后端，离线模式不可用。</p>
      </GlassCard>
    );
  }

  const rows = data?.items ?? [];

  return (
    <GlassCard
      title="HS Code 速查"
      description="按关键词、品类与市场检索默认 HS6 编码"
    >
      <div className="grid gap-3 lg:grid-cols-[1fr_1fr_1fr_auto] lg:items-end">
        <label className="grid gap-1.5">
          <span className="text-xs font-semibold text-slate-400">关键词</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="例如 1905 或 辣条"
            className="glass-inset focus-ring h-10 w-full px-3 text-sm"
          />
        </label>
        <label className="grid gap-1.5">
          <span className="text-xs font-semibold text-slate-400">品类</span>
          <Select
            value={category}
            onValueChange={setCategory}
            options={[{ value: "", label: "全部品类" }, ...categoryOptions]}
          />
        </label>
        <label className="grid gap-1.5">
          <span className="text-xs font-semibold text-slate-400">市场</span>
          <Select
            value={market}
            onValueChange={setMarket}
            options={[{ value: "", label: "全部市场" }, ...marketOptions]}
          />
        </label>
        <Button onClick={() => setEnabled(true)} disabled={isLoading}>
          <SearchCode className="h-4 w-4" />
          {isLoading ? "检索中..." : "检索"}
        </Button>
      </div>

      <div className="mt-4">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>品类</TableHead>
              <TableHead>HS Code</TableHead>
              <TableHead>描述</TableHead>
              <TableHead>关税</TableHead>
              <TableHead>状态</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.category}>
                <TableCell className="font-semibold text-white">
                  {categoryName(row.category)}
                </TableCell>
                <TableCell className="font-mono text-accent">{row.hs_code}</TableCell>
                <TableCell className="max-w-[260px]">{row.description}</TableCell>
                <TableCell className="tabular">
                  {row.base_tariff_rate != null ? `${(Number(row.base_tariff_rate) * 100).toFixed(1)}%` : "--"}
                </TableCell>
                <TableCell>
                  <Badge tone={row.verified ? "green" : "amber"}>
                    {row.verified ? "已核实" : "待核实"}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
            {!rows.length && !isLoading && (
              <TableRow>
                <TableCell colSpan={5} className="text-center text-slate-500">
                  输入条件后点击“检索”
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </GlassCard>
  );
}
