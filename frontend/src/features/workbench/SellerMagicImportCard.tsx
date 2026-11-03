import { useRef, useState } from "react";
import {
  ArrowRight,
  ListChecks,
  Upload,
} from "lucide-react";
import { useSellerMagicImport } from "@/shared/api/hooks";
import { IS_OFFLINE } from "@/shared/api/offline";
import type { SellerMagicImportResult } from "@/shared/api/types";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { GlassCard } from "@/shared/ui/glass-card";
import { useTradeIntelStore } from "@/shared/store/trade-intel";
import { useTransitionNavigate } from "@/widgets/RouteTransition";

export function SellerMagicImportCard() {
  const transitionNavigate = useTransitionNavigate();
  const setSelectionDraft = useTradeIntelStore((state) => state.setSelectionDraft);
  const importMutation = useSellerMagicImport();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<SellerMagicImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFile = (event: React.ChangeEvent<HTMLInputElement>) => {
    setFile(event.target.files?.[0] ?? null);
    setResult(null);
    setError(null);
  };

  const upload = async () => {
    if (!file) return;
    setError(null);
    try {
      const data = await importMutation.mutateAsync(file);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "导入失败");
    }
  };

  const analyzeKeyword = (keyword: string) => {
    setSelectionDraft({
      label: keyword,
      keyword,
      market: "us",
      category: undefined,
    });
    transitionNavigate("/workbench?tab=four-brain");
  };

  if (IS_OFFLINE) {
    return (
      <GlassCard>
        <p className="text-sm text-slate-400">
          卖家精灵 CSV 导入需要在线后端，离线模式不可用。
        </p>
      </GlassCard>
    );
  }

  return (
    <div className="grid gap-4">
      <GlassCard title="卖家精灵 CSV 导入" description="把竞品工具的关键词导出变成系统上游入口" strong>
        <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
          <label className="grid gap-1.5">
            <span className="text-xs font-semibold text-slate-400">选择 CSV 文件</span>
            <input
              ref={inputRef}
              type="file"
              accept=".csv"
              onChange={handleFile}
              className="glass-inset focus-ring w-full px-3 py-2.5 text-xs text-slate-300 file:mr-3 file:rounded-lg file:border-0 file:bg-cyan-400/15 file:px-3 file:py-1.5 file:text-accent"
            />
          </label>
          <Button onClick={() => void upload()} disabled={!file || importMutation.isPending}>
            <Upload className="h-4 w-4" />
            {importMutation.isPending ? "导入中..." : "上传并映射"}
          </Button>
        </div>
        <p className="mt-3 text-[11px] leading-4 text-slate-500">
          自动识别“关键词/搜索热度/月销量/平均价格/竞争度/评分”等常见导出列，必需列为关键词。
        </p>
      </GlassCard>

      {error && (
        <GlassCard>
          <p className="text-sm text-red-300">{error}</p>
        </GlassCard>
      )}

      {result && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <ImportStat label="有效行数" value={String(result.summary.rows)} />
            <ImportStat label="关键词数" value={String(result.summary.keyword_count)} />
            <ImportStat
              label="平均价格"
              value={result.summary.avg_price != null ? `$${result.summary.avg_price.toFixed(2)}` : "--"}
            />
            <ImportStat label="匹配列数" value={String(result.summary.matched_columns)} />
          </div>

          <GlassCard title="字段映射摘要" description={`${result.file} · 映射 ${result.summary.matched_columns} 列`}>
            <div className="flex flex-wrap gap-2">
              {(result.summary.numeric_columns ?? []).map((column) => (
                <Badge key={column} tone="cyan">{column}</Badge>
              ))}
              {(result.summary.unmatched_columns ?? []).length > 0 && (
                <Badge tone="amber">
                  未识别 {(result.summary.unmatched_columns ?? []).slice(0, 6).join(" / ")}
                </Badge>
              )}
              {result.summary.dropped_rows > 0 && (
                <Badge tone="red">截断 {result.summary.dropped_rows} 行</Badge>
              )}
            </div>
          </GlassCard>

          {(result.top_keywords ?? []).length > 0 && (
            <GlassCard title="Top 关键词" description="导入结果可直接带入四脑分析">
              <div className="grid gap-2">
                {(result.top_keywords ?? []).map((item, index) => (
                  <div key={`${item.keyword}-${index}`} className="glass-soft flex flex-wrap items-center gap-2 p-3">
                    <ListChecks className="h-4 w-4 shrink-0 text-accent" />
                    <span className="min-w-0 flex-1 truncate text-sm font-semibold text-white">
                      {item.keyword ?? "--"}
                    </span>
                    {item.avg_price != null && (
                      <span className="tabular text-xs text-slate-400">
                        ${item.avg_price.toFixed(2)}
                      </span>
                    )}
                    <Button size="sm" variant="outline" onClick={() => analyzeKeyword(String(item.keyword ?? ""))}>
                      去四脑分析
                      <ArrowRight className="h-3 w-3" />
                    </Button>
                  </div>
                ))}
              </div>
            </GlassCard>
          )}
        </>
      )}
    </div>
  );
}

function ImportStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="glass-inset p-3">
      <p className="text-[11px] font-semibold text-slate-500">{label}</p>
      <p className="tabular mt-1 text-lg font-extrabold text-white">{value}</p>
    </div>
  );
}
