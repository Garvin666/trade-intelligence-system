import { useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Minimize2, Maximize2 } from "lucide-react";
import { Button } from "@/shared/ui/button";
import { Badge } from "@/shared/ui/badge";
import { MarkdownView } from "./MarkdownView";

const MAX_PAGE_LINES = 80;
const MAX_PAGE_CHARS = 2400;

export function PagedMarkdown({ content }: { content: string }) {
  const [page, setPage] = useState(0);
  const [compact, setCompact] = useState(false);
  const pages = useMemo(() => splitPages(content), [content]);

  if (pages.length <= 1 && !compact) {
    return (
      <div className="markdown-body">
        <MarkdownView content={content} />
      </div>
    );
  }

  const safePage = Math.min(page, pages.length - 1);
  const visible = compact ? pages[0] : pages[safePage];

  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="cyan">
            {compact ? "摘要视图" : `${safePage + 1} / ${pages.length} 页`}
          </Badge>
          {pages.length > 1 && (
            <>
              <Button
                size="sm"
                variant="outline"
                disabled={safePage === 0 || compact}
                onClick={() => setPage((value) => Math.max(0, value - 1))}
              >
                <ChevronLeft className="h-3.5 w-3.5" />
                上一页
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={safePage >= pages.length - 1 || compact}
                onClick={() =>
                  setPage((value) => Math.min(pages.length - 1, value + 1))
                }
              >
                下一页
                <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </>
          )}
        </div>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => setCompact((value) => !value)}
        >
          {compact ? (
            <>
              <Maximize2 className="h-3.5 w-3.5" />
              展开全文
            </>
          ) : (
            <>
              <Minimize2 className="h-3.5 w-3.5" />
              收缩
            </>
          )}
        </Button>
      </div>
      <div className="glass-soft p-4">
        <MarkdownView content={visible} />
      </div>
    </div>
  );
}

function splitPages(content: string): string[] {
  const lines = content.split(/\r?\n/);
  if (lines.length <= MAX_PAGE_LINES && content.length <= MAX_PAGE_CHARS) {
    return [content.trim()];
  }

  const pages: string[] = [];
  let current: string[] = [];
  let currentLines = 0;
  let currentChars = 0;

  const flush = () => {
    const text = current.join("\n").trim();
    if (text) pages.push(text);
    current = [];
    currentLines = 0;
    currentChars = 0;
  };

  for (const line of lines) {
    const trimmed = line.trim();
    const isHeading = /^#{1,6}\s/.test(trimmed);
    const isBlank = trimmed === "";
    const shouldBreak =
      current.length > 0 &&
      (currentChars > MAX_PAGE_CHARS || currentLines >= MAX_PAGE_LINES) &&
      (isHeading || isBlank);
    if (shouldBreak) {
      flush();
    }
    current.push(line);
    currentChars += line.length + 1;
    currentLines += 1;
  }
  flush();

  return pages.length ? pages : [content.trim()];
}
