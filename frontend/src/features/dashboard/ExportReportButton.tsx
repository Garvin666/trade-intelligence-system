import { Download, FileDown } from "lucide-react";
import type { DashboardQuery } from "@/shared/api/client";
import { useExportReport } from "@/shared/api/hooks";
import { IS_OFFLINE } from "@/shared/api/offline";
import type { Recommendation } from "@/shared/api/types";
import { Button } from "@/shared/ui/button";

export function ExportReportButton({
  filters,
  recommendations,
  conclusion,
}: {
  filters: DashboardQuery;
  recommendations?: Recommendation[];
  conclusion?: string;
}) {
  const exportReport = useExportReport();
  const recommendation = recommendations?.[0];

  const run = async (format: "md" | "pdf") => {
    const blob = await exportReport.mutateAsync({
      format,
      filters,
      recommendation,
      evidence: [],
      conclusion: conclusion ?? "基于当前看板筛选与推荐生成。",
      generated_at: new Date().toISOString(),
    });
    saveBlob(blob, `dashboard_selection_report.${format}`);
  };

  return (
    <div className="flex flex-wrap gap-2">
      <Button size="sm" variant="outline" disabled={IS_OFFLINE || exportReport.isPending} onClick={() => run("md")}>
        <FileDown className="h-4 w-4" />
        {exportReport.isPending ? "导出中..." : "导出 MD"}
      </Button>
      <Button size="sm" variant="outline" disabled={IS_OFFLINE || exportReport.isPending} onClick={() => run("pdf")}>
        <Download className="h-4 w-4" />
        导出 PDF
      </Button>
    </div>
  );
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
