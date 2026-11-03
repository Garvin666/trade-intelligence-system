import { BookOpenCheck, ExternalLink } from "lucide-react";
import { useEvidenceLedger } from "@/shared/api/hooks";
import { IS_OFFLINE } from "@/shared/api/offline";
import type { EvidenceLedgerItem } from "@/shared/api/types";
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

function expiryTone(status?: string): "red" | "amber" | "green" | "neutral" {
  if (status === "expired") return "red";
  if (status === "expiring_soon") return "amber";
  if (status === "valid") return "green";
  return "neutral";
}

function expiryLabel(status?: string): string {
  if (status === "expired") return "已过期";
  if (status === "expiring_soon") return "即将过期";
  if (status === "valid") return "有效";
  return "长期有效";
}

export function EvidenceLedgerPanel() {
  const { data, isLoading, isError } = useEvidenceLedger();

  if (IS_OFFLINE) {
    return (
      <GlassCard>
        <p className="text-sm text-slate-400">证据账本需要在线后端读取政策与 HS 快照，离线模式不可用。</p>
      </GlassCard>
    );
  }

  if (isLoading && !data) {
    return (
      <GlassCard>
        <div className="h-32 animate-pulse rounded-lg bg-white/5" />
      </GlassCard>
    );
  }

  if (isError || !data) {
    return (
      <GlassCard>
        <p className="text-sm text-red-300">证据账本加载失败，请确认后端已启动。</p>
      </GlassCard>
    );
  }

  return (
    <GlassCard
      title="证据账本"
      description="政策事件与 HS6 速查条目的来源、抓取时间、生效日、有效期与复核状态，逐条可回溯。"
      strong
    >
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Badge tone="cyan">
          <BookOpenCheck className="h-3.5 w-3.5" />
          {data.count} 条记录
        </Badge>
        <Badge tone={data.expired_count > 0 ? "red" : "green"}>
          {data.expired_count > 0 ? `${data.expired_count} 条已过期` : "无过期记录"}
        </Badge>
        <span className="text-[11px] text-slate-500">schema v{data.schema_version}</span>
      </div>

      <div className="max-h-[520px] overflow-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>条目</TableHead>
              <TableHead>来源</TableHead>
              <TableHead>抓取时间</TableHead>
              <TableHead>生效日</TableHead>
              <TableHead>有效期</TableHead>
              <TableHead>HS 版本</TableHead>
              <TableHead>公式 / 口径</TableHead>
              <TableHead>复核</TableHead>
              <TableHead>状态</TableHead>
              <TableHead></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.items.map((item, index) => (
              <LedgerRow key={item.key ?? index} item={item} />
            ))}
          </TableBody>
        </Table>
      </div>
    </GlassCard>
  );
}

function LedgerRow({ item }: { item: EvidenceLedgerItem }) {
  const expiry = item.expiry_status?.status;
  return (
    <TableRow>
      <TableCell className="max-w-[220px]">
        <p className="truncate font-semibold text-white" title={item.title ?? undefined}>
          {item.title ?? item.key ?? "--"}
        </p>
        <p className="mt-0.5 font-mono text-[10px] text-slate-500">{item.key ?? ""}</p>
      </TableCell>
      <TableCell className="max-w-[180px]">
        <span className="line-clamp-2 text-xs" title={item.source ?? undefined}>
          {item.source ?? "--"}
        </span>
      </TableCell>
      <TableCell className="font-mono text-xs">{item.fetched_at ?? "--"}</TableCell>
      <TableCell className="font-mono text-xs">{item.effective_date ?? "--"}</TableCell>
      <TableCell>
        <div className="flex flex-col gap-1">
          <span className="font-mono text-[11px] text-slate-400">
            {item.expires_at ?? "长期有效"}
          </span>
          <Badge tone={expiryTone(expiry)}>{expiryLabel(expiry)}</Badge>
        </div>
      </TableCell>
      <TableCell className="text-xs">{item.hs_version ?? "--"}</TableCell>
      <TableCell className="max-w-[220px]">
        <span className="line-clamp-2 text-xs" title={item.formula ?? undefined}>
          {item.formula ?? "--"}
        </span>
      </TableCell>
      <TableCell>
        <Badge tone={item.review_status === "已核实" ? "green" : "amber"}>
          {item.review_status ?? "--"}
        </Badge>
      </TableCell>
      <TableCell>
        <Badge tone={item.status === "已核实" ? "green" : "neutral"}>
          {item.status ?? "--"}
        </Badge>
      </TableCell>
      <TableCell>
        {item.url ? (
          <a
            href={item.url ?? undefined}
            target="_blank"
            rel="noreferrer"
            className="focus-ring rounded-lg p-1.5 text-slate-400 hover:text-accent"
            aria-label="打开来源"
          >
            <ExternalLink className="h-4 w-4" />
          </a>
        ) : null}
      </TableCell>
    </TableRow>
  );
}
