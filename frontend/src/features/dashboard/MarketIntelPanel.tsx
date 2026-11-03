import { Boxes, Gauge, ShieldAlert, TrendingUp } from "lucide-react";
import type { DashboardQuery } from "@/shared/api/client";
import { useMarketIntel } from "@/shared/api/hooks";
import { IS_OFFLINE } from "@/shared/api/offline";
import type { RankingRow, RiskRow, CostRow } from "@/shared/api/types";
import { categoryName, marketName } from "@/shared/lib/names";
import { Badge } from "@/shared/ui/badge";
import { GlassCard } from "@/shared/ui/glass-card";
import { Skeleton } from "@/shared/ui/skeleton";
import { KpiValue } from "@/shared/ui/data";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/ui/table";

export function MarketIntelPanel({ filters }: { filters: DashboardQuery }) {
  const { data, isLoading, isError } = useMarketIntel(filters);

  if (IS_OFFLINE) {
    return (
      <GlassCard>
        <p className="text-sm text-slate-400">
          市场情报需要在线后端读取榜单、风险、成本与海关数据，离线模式暂不提供。
        </p>
      </GlassCard>
    );
  }

  if (isLoading && !data) {
    return (
      <div className="grid gap-4">
        <GlassCard className="p-5">
          <Skeleton className="h-40" />
          <p className="mt-3 text-sm text-slate-400">正在加载市场情报…</p>
        </GlassCard>
        <GlassCard className="p-5">
          <Skeleton className="h-40" />
          <p className="mt-3 text-sm text-slate-400">正在同步榜单、风险与成本数据…</p>
        </GlassCard>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <GlassCard>
        <p className="text-sm text-red-300">市场情报加载失败，请确认后端已启动。</p>
      </GlassCard>
    );
  }

  const {
    rankings,
    risk,
    cost,
    compare,
    reviews,
    exportValue,
    competition,
    searchTrends,
    status,
  } = data;
  const rankingsStatus = (status?.platform_rankings ?? {}) as Record<string, unknown>;
  const trendsStatus = (status?.trends ?? {}) as Record<string, unknown>;
  const customsStatus = (status?.customs ?? {}) as Record<string, unknown>;
  const trendsCoverage = (searchTrends.coverage ?? trendsStatus.coverage ?? {}) as Record<
    string,
    unknown
  >;
  const rankingDetail = `${int(rankings.real_count)} 真实 / ${int(rankings.mock_count)} 回退`;
  const trendsDetail = `真实 ${int(trendsCoverage.real)} / 模拟 ${int(trendsCoverage.mock)}`;
  const rankingsSourceLevel =
    typeof rankings.source_level === "string"
      ? rankings.source_level
      : String(rankingsStatus.source_level ?? "平台榜单快照");
  const customsPeriod = String(customsStatus.period ?? exportValue.period ?? "");
  const customsProvider = customsProviderLabel(
    String(customsStatus.provider ?? exportValue.provider ?? ""),
  );
  const customsDetail = `中国出口${customsPeriod ? ` ${customsPeriod}` : ""} · ${customsProvider}`;

  return (
    <div className="grid gap-4">
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <Metric
          icon={Boxes}
          label="平台榜单"
          value={`${rankings?.count ?? 0} 条`}
          detail={rankingDetail}
        />
        <Metric icon={ShieldAlert} label="风险条目" value={`${risk?.count ?? 0} 条`} />
        <Metric icon={Gauge} label="成本估算" value={`${cost?.count ?? 0} 条`} />
        <Metric
          icon={TrendingUp}
          label="搜索趋势"
          value={`${searchTrends?.count ?? 0} 条`}
          detail={trendsDetail}
        />
      </div>

      <GlassCard
        title="平台榜单"
        description={rankingsSourceLevel}
        action={
          rankings.fallback_used !== undefined ? (
            <Badge tone={rankings.fallback_used ? "amber" : "green"}>
              {rankings.fallback_used ? "含回退" : "真实"}
            </Badge>
          ) : undefined
        }
      >
        <RankingTable rows={(rankings?.items ?? []).slice(0, 20)} />
      </GlassCard>

      <div className="grid gap-4 xl:grid-cols-2">
        <GlassCard
          title="经营风险"
          description="特征口径（合成 + 真实特征）"
        >
          <RiskTable rows={(risk?.items ?? []).slice(0, 20)} />
        </GlassCard>
        <GlassCard
          title="成本结构"
          description="特征口径（合成 + 真实特征）"
        >
          <CostTable rows={(cost?.items ?? []).slice(0, 20)} />
        </GlassCard>
      </div>

      <GlassCard
        title="市场对比"
        description="各市场销量、竞争、价格与出口均值（特征口径）"
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>市场</TableHead>
              <TableHead>平均销量</TableHead>
              <TableHead>竞争度</TableHead>
              <TableHead>价格中位数</TableHead>
              <TableHead>出口金额</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(compare?.items ?? []).map((row) => (
              <TableRow key={String(row.market)}>
                <TableCell className="font-semibold text-white">{String(row.market_name ?? row.market)}</TableCell>
                <TableCell className="tabular">{num(row.avg_sales_volume)}</TableCell>
                <TableCell className="tabular">{num(row.avg_competition_index)}</TableCell>
                <TableCell className="tabular">{num(row.avg_price_median)}</TableCell>
                <TableCell className="tabular">{num(row.avg_export_value)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </GlassCard>

      <div className="grid gap-4 xl:grid-cols-3">
        <GlassCard title="评论增长" description="评论增长趋势（特征口径）">
          <SimpleList rows={(reviews?.items ?? []).slice(0, 12)} label="review_growth" />
        </GlassCard>
        <GlassCard title="出口金额" description={customsDetail}>
          <SimpleList rows={(exportValue?.items ?? []).slice(0, 12)} label="export_value" />
        </GlassCard>
        <GlassCard title="竞争指数" description="竞争指数（特征口径）">
          <SimpleList rows={(competition?.items ?? []).slice(0, 12)} label="competition_index" />
        </GlassCard>
      </div>
    </div>
  );
}

function RankingTable({ rows }: { rows: RankingRow[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>排名</TableHead>
          <TableHead>组合</TableHead>
          <TableHead>平台</TableHead>
          <TableHead>标题</TableHead>
          <TableHead>价格</TableHead>
          <TableHead>评分</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row, index) => (
          <TableRow key={`${row.platform}-${index}`}>
            <TableCell className="font-mono text-slate-400">#{row.rank ?? index + 1}</TableCell>
            <TableCell className="font-semibold text-white">
              {categoryName(String(row.category ?? ""))} × {marketName(String(row.market ?? ""))}
            </TableCell>
            <TableCell>
              <Badge tone={row.fallback_used ? "amber" : "cyan"}>
                {platformLabel(row.platform)}
              </Badge>
            </TableCell>
            <TableCell className="max-w-[260px] truncate">{row.title ?? "--"}</TableCell>
            <TableCell className="tabular">{row.price != null ? `$${Number(row.price).toFixed(2)}` : "--"}</TableCell>
            <TableCell className="tabular text-accent">{num(row.score)}</TableCell>
          </TableRow>
        ))}
        {!rows.length && (
          <TableRow>
            <TableCell colSpan={6} className="text-center text-slate-500">
              暂无榜单数据
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}

function RiskTable({ rows }: { rows: RiskRow[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>组合</TableHead>
          <TableHead>风险分</TableHead>
          <TableHead>等级</TableHead>
          <TableHead>原因</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row, index) => (
          <TableRow key={`${row.category}-${row.market}-${index}`}>
            <TableCell className="font-semibold text-white">
              {categoryName(String(row.category ?? ""))} × {marketName(String(row.market ?? ""))}
            </TableCell>
            <TableCell className="tabular">{num(row.risk_score)}</TableCell>
            <TableCell>
              <Badge tone={row.risk_level === "high" ? "red" : row.risk_level === "medium" ? "amber" : "green"}>
                {row.risk_level ?? "--"}
              </Badge>
            </TableCell>
            <TableCell className="max-w-[220px] truncate">{row.risk_reason ?? "--"}</TableCell>
          </TableRow>
        ))}
        {!rows.length && (
          <TableRow>
            <TableCell colSpan={4} className="text-center text-slate-500">
              暂无风险数据
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}

function CostTable({ rows }: { rows: CostRow[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>组合</TableHead>
          <TableHead>毛利</TableHead>
          <TableHead>物流</TableHead>
          <TableHead>退货率</TableHead>
          <TableHead>广告成本</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row, index) => (
          <TableRow key={`${row.category}-${row.market}-${index}`}>
            <TableCell className="font-semibold text-white">
              {categoryName(String(row.category ?? ""))} × {marketName(String(row.market ?? ""))}
            </TableCell>
            <TableCell className="tabular text-emerald-300">{num(row.gross_margin)}</TableCell>
            <TableCell className="tabular">{num(row.logistics_cost)}</TableCell>
            <TableCell className="tabular">{num(row.return_rate)}</TableCell>
            <TableCell className="tabular">{num(row.ad_cost_index)}</TableCell>
          </TableRow>
        ))}
        {!rows.length && (
          <TableRow>
            <TableCell colSpan={5} className="text-center text-slate-500">
              暂无成本数据
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  );
}

function SimpleList({ rows, label }: { rows: Record<string, unknown>[]; label: string }) {
  return (
    <div className="grid gap-2">
      {rows.map((row, index) => (
        <div key={index} className="glass-soft flex items-center justify-between gap-2 p-2.5">
          <span className="truncate text-xs text-slate-300">
            {categoryName(String(row.category))} ×{" "}
            {String(row.market_name ?? marketName(String(row.market)))}
          </span>
          <span className="tabular shrink-0 text-sm font-bold text-accent">{num(row[label])}</span>
        </div>
      ))}
      {!rows.length && <p className="text-xs text-slate-500">暂无数据</p>}
    </div>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
  detail,
}: {
  icon: typeof Boxes;
  label: string;
  value: string;
  detail?: string;
}) {
  return (
    <GlassCard className="p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold text-slate-400">{label}</p>
          <KpiValue className="mt-1" value={value} />
          {detail && <p className="mt-1 text-[11px] leading-4 text-slate-500">{detail}</p>}
        </div>
        <div className="glass-inset grid h-10 w-10 place-items-center rounded-lg text-accent">
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </GlassCard>
  );
}

function int(value: unknown): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function platformLabel(value: unknown): string {
  const labels: Record<string, string> = {
    amazon_github: "Amazon 样例",
    ebay_github: "eBay 样例",
    shopee_github: "Shopee 样例",
    amazon_bestsellers: "Amazon 榜单",
    mock: "模拟",
  };
  const key = String(value ?? "");
  return labels[key] ?? (key || "--");
}

function customsProviderLabel(value: unknown): string {
  const labels: Record<string, string> = {
    comtrade: "UN Comtrade",
    ots: "Open Trade Statistics",
    mock: "模拟",
  };
  const key = String(value ?? "");
  return labels[key] ?? (key || "--");
}

function num(value: unknown): string {
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(2);
  if (typeof value === "string") return value;
  return "--";
}
