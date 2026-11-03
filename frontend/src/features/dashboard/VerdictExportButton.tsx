import { useState } from "react";
import { Download, Send, ShieldCheck } from "lucide-react";
import { useExportVerdicts } from "@/shared/api/hooks";
import { IS_OFFLINE } from "@/shared/api/offline";
import type { Recommendation } from "@/shared/api/types";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTrigger,
} from "@/shared/ui/dialog";

export function VerdictExportButton({ rows }: { rows: Recommendation[] }) {
  const exportVerdicts = useExportVerdicts();
  const [webhookUrl, setWebhookUrl] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  const run = async (push: boolean) => {
    if (!rows.length) return;
    setMessage(null);
    try {
      const result = await exportVerdicts.mutateAsync({
        rows: rows.map((row) => ({
          category: row.category,
          market: row.market,
          verdict: row.verdict,
          score: row.six_dimension_score,
          generated_at: new Date().toISOString(),
        })),
        webhook_url: push ? webhookUrl.trim() || undefined : undefined,
      });
      downloadCsv(result.csv);
      if (push) {
        setMessage(
          result.webhook?.status === "ok"
            ? `已导出 ${result.row_count} 行并推送（HTTP ${result.webhook.http}）`
            : result.webhook?.status === "warning"
              ? `已导出 ${result.row_count} 行；Webhook 推送失败：${result.webhook.detail ?? "未知错误"}`
              : `已导出 ${result.row_count} 行`,
        );
      } else {
        setMessage(`已导出 ${result.row_count} 行 Go/No-Go CSV`);
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "导出失败");
    }
  };

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button
          size="sm"
          variant="outline"
          disabled={IS_OFFLINE || !rows.length}
        >
          <ShieldCheck className="h-3.5 w-3.5" />
          导出 Go/No-Go
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader
          title="导出 Go/No-Go 结论"
          description={`将当前 ${rows.length} 条推荐结论导出为带证据链字段的 CSV，可选推送到企业 Webhook。`}
        />
        <div className="grid gap-4">
          <label className="grid gap-1.5">
            <span className="text-xs font-semibold text-slate-400">Webhook URL（可选）</span>
            <input
              value={webhookUrl}
              onChange={(event) => setWebhookUrl(event.target.value)}
              placeholder="https://example.com/hooks/verdicts"
              className="glass-inset focus-ring h-10 w-full px-3 text-sm"
            />
          </label>
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Button
              variant="outline"
              disabled={exportVerdicts.isPending}
              onClick={() => void run(false)}
            >
              <Download className="h-4 w-4" />
              {exportVerdicts.isPending ? "导出中..." : "仅导出 CSV"}
            </Button>
            <Button
              disabled={exportVerdicts.isPending || !webhookUrl.trim()}
              onClick={() => void run(true)}
            >
              <Send className="h-4 w-4" />
              导出并推送
            </Button>
          </div>
          {message && (
            <div className="flex items-center gap-2">
              <Badge tone={message.includes("失败") ? "red" : "green"}>{message}</Badge>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

function downloadCsv(csv: string) {
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "go_nogo_verdicts.csv";
  anchor.click();
  URL.revokeObjectURL(url);
}
