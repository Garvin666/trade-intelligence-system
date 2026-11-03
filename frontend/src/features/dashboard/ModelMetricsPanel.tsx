import { useModelMetrics } from "@/shared/api/hooks";
import type { DashboardQuery } from "@/shared/api/client";
import { IS_OFFLINE } from "@/shared/api/offline";
import { categoryName, marketName } from "@/shared/lib/names";
import { Badge } from "@/shared/ui/badge";
import { GlassCard } from "@/shared/ui/glass-card";
import { Skeleton } from "@/shared/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/ui/table";

const modelLabels: Record<string, string> = {
  prophet_baseline: "Prophet 基线",
  lightgbm_advanced: "LightGBM 进阶",
  statsforecast: "StatsForecast",
};

export function ModelMetricsPanel({ filters }: { filters: DashboardQuery }) {
  const { data, isLoading, isError } = useModelMetrics(filters);

  if (IS_OFFLINE) {
    return (
      <GlassCard>
        <p className="text-sm text-slate-400">模型评估需要在线后端读取模型指标，离线快照暂不提供。</p>
      </GlassCard>
    );
  }

  if (isLoading && !data) {
    return (
      <GlassCard className="p-5">
        <Skeleton className="h-48" />
        <p className="mt-3 text-sm text-slate-400">正在加载模型指标…</p>
      </GlassCard>
    );
  }

  if (isError || !data) {
    return (
      <GlassCard>
        <p className="text-sm text-red-300">模型指标加载失败。</p>
      </GlassCard>
    );
  }

  const groups = [
    { key: "baseline", label: "Prophet 基线", rows: data.baseline ?? [] },
    { key: "advanced", label: "LightGBM 进阶", rows: data.advanced ?? [] },
    { key: "statsforecast", label: "StatsForecast", rows: data.statsforecast ?? [] },
  ];

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap gap-2">
        {groups.map((group) => (
          <Badge key={group.key} tone="cyan">
            {group.label}: {group.rows.length} 条
          </Badge>
        ))}
      </div>
      {groups.map((group) => (
        <GlassCard key={group.key} title={group.label} description="回测 MAPE / MAE">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>组合</TableHead>
                <TableHead>模型</TableHead>
                <TableHead>MAPE</TableHead>
                <TableHead>MAE</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {group.rows.map((row, index) => (
                <TableRow key={`${group.key}-${index}`}>
                  <TableCell className="font-semibold text-white">
                    {categoryName(row.category)} × {marketName(row.market)}
                  </TableCell>
                  <TableCell>{modelLabels[row.model] ?? row.model}</TableCell>
                  <TableCell className="tabular text-accent">{row.mape?.toFixed(4)}</TableCell>
                  <TableCell className="tabular">{row.mae?.toFixed(4)}</TableCell>
                </TableRow>
              ))}
              {!group.rows.length && (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-slate-500">
                    暂无数据
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </GlassCard>
      ))}
      <BusinessMetricsSection metrics={data.business_metrics} />
    </div>
  );
}

function BusinessMetricsSection({
  metrics,
}: {
  metrics?: Record<string, unknown>;
}) {
  const calibration = (metrics?.calibration ?? {}) as Record<string, unknown>;
  const direction = (metrics?.direction_hit_rate ?? {}) as Record<string, unknown>;
  const topn = (metrics?.topn_posterior_return ?? {}) as Record<string, unknown>;
  const inventory = (metrics?.inventory_loss ?? {}) as Record<string, unknown>;
  const aggregates = (inventory.aggregates ?? {}) as Record<string, unknown>;
  const scope = (metrics?.scope ?? {}) as Record<string, unknown>;
  const rows = Array.isArray(topn.rows)
    ? (topn.rows as Record<string, unknown>[])
    : [];
  const posteriorTotal = rows.reduce(
    (sum, row) => sum + num(row.posterior_return_90d_usd),
    0,
  );

  if (!metrics || calibration.status !== "ok") {
    return (
      <GlassCard
        title="业务指标（回测后验）"
        description="预测校准度 / 方向命中率 / Top-N 后验收益 / 库存损失"
      >
        <p className="text-sm text-slate-500">
          未生成回测业务指标，请先运行 scripts/rolling_backtest.py。
        </p>
      </GlassCard>
    );
  }

  return (
    <GlassCard
      title="业务指标（回测后验）"
      description={`${num(scope.combos)} 组合 · ${num(scope.prediction_points)} 个预测点 · 滚动回测口径`}
      strong
    >
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="预测校准度"
          value={`MAPE ${pct(calibration.mape_pct)}`}
          detail={`区间覆盖 ${pct(calibration.interval_coverage_pct)} / 名义 ${pct(calibration.interval_nominal_pct)}`}
        />
        <MetricCard
          label="方向命中率"
          value={pct(direction.hit_rate_pct)}
          detail={`上升 ${pct(direction.up_hit_rate_pct)} · 下降 ${pct(direction.down_hit_rate_pct)}`}
        />
        <MetricCard
          label="Top-N 后验收益"
          value={usd(posteriorTotal)}
          detail={`Top ${num(topn.top_n || topn.n || 10)} · ${num(topn.horizon_days || 90)} 天`}
        />
        <MetricCard
          label="库存损失估算"
          value={usd(aggregates.total_loss_annual_usd)}
          detail={`每组合年化 ${usd(aggregates.avg_loss_annual_per_combo_usd)}`}
        />
      </div>

      {rows.length > 0 && (
        <div className="mt-4 max-h-[360px] overflow-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-right">排名</TableHead>
                <TableHead>组合</TableHead>
                <TableHead className="text-right">实际增长</TableHead>
                <TableHead className="text-right">预测增长</TableHead>
                <TableHead className="text-right">90 天后验收益</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={`${row.rank}-${row.category}-${row.market}`}>
                  <TableCell className="font-mono text-right text-slate-400">
                    #{num(row.rank)}
                  </TableCell>
                  <TableCell className="font-semibold text-white">
                    {categoryName(String(row.category))} × {marketName(String(row.market))}
                  </TableCell>
                  <TableCell className="tabular text-right text-emerald-300">
                    {pct(row.realized_growth_pct)}
                  </TableCell>
                  <TableCell className="tabular text-right">{pct(row.forecast_growth_pct)}</TableCell>
                  <TableCell className="tabular text-right text-accent">
                    {usd(row.posterior_return_90d_usd)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </GlassCard>
  );
}

function MetricCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="glass-inset p-3">
      <p className="text-[11px] font-semibold text-slate-500">{label}</p>
      <p className="tabular mt-1 text-lg font-extrabold text-white">{value}</p>
      <p className="mt-1 text-[10px] leading-4 text-slate-500">{detail}</p>
    </div>
  );
}

function num(value: unknown): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function pct(value: unknown): string {
  return `${num(value).toFixed(1)}%`;
}

function usd(value: unknown): string {
  const amount = num(value);
  if (amount >= 1_000_000) return `$${(amount / 1_000_000).toFixed(2)}M`;
  return `$${amount.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}
