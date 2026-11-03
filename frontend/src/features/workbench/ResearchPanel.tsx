import { useState } from "react";
import { ExternalLink, Search } from "lucide-react";
import { fetchResearch, fetchSearch } from "@/shared/api/client";
import { IS_OFFLINE } from "@/shared/api/offline";
import type { ResearchResult, SearchResult } from "@/shared/api/types";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { GlassCard } from "@/shared/ui/glass-card";

export function ResearchPanel() {
  const [keyword, setKeyword] = useState("辣条（网红休闲零食）");
  const [market, setMarket] = useState("us");
  const [maxResults, setMaxResults] = useState(5);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [research, setResearch] = useState<ResearchResult | null>(null);
  const [search, setSearch] = useState<SearchResult | null>(null);

  const run = async (mode: "search" | "research") => {
    setLoading(true);
    setError(null);
    try {
      if (mode === "search") {
        setSearch(await fetchSearch(`${keyword} ${market} 跨境电商`, maxResults));
      } else {
        setResearch(
          await fetchResearch({
            keyword,
            market,
            max_results: maxResults,
          }),
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "联网检索失败");
    } finally {
      setLoading(false);
    }
  };

  if (IS_OFFLINE) {
    return (
      <GlassCard>
        <p className="text-sm text-slate-400">联网研究需要在线后端，离线模式不可用。</p>
      </GlassCard>
    );
  }

  return (
    <div className="grid gap-4">
      <GlassCard title="联网研究" description="多查询检索并汇总来源，无需 API Key">
        <div className="grid gap-3 sm:grid-cols-[1fr_160px_120px_auto] sm:items-end">
          <label className="grid gap-1.5">
            <span className="text-xs font-semibold text-slate-400">关键词</span>
            <input
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              className="glass-inset focus-ring h-10 w-full px-3 text-sm text-slate-200"
            />
          </label>
          <label className="grid gap-1.5">
            <span className="text-xs font-semibold text-slate-400">市场</span>
            <input
              value={market}
              onChange={(event) => setMarket(event.target.value)}
              className="glass-inset focus-ring h-10 w-full px-3 text-sm text-slate-200"
            />
          </label>
          <label className="grid gap-1.5">
            <span className="text-xs font-semibold text-slate-400">条数</span>
            <input
              type="number"
              min={1}
              max={20}
              value={maxResults}
              onChange={(event) => setMaxResults(Number(event.target.value))}
              className="glass-inset focus-ring h-10 w-full px-3 text-sm text-slate-200"
            />
          </label>
          <div className="flex gap-2">
            <Button variant="secondary" disabled={loading} onClick={() => run("search")}>
              <Search className="h-4 w-4" />
              直接搜索
            </Button>
            <Button disabled={loading} onClick={() => run("research")}>
              联网研究
            </Button>
          </div>
        </div>
      </GlassCard>

      {error && <p className="text-xs text-red-300">{error}</p>}

      {search && (
        <GlassCard
          title="搜索结果"
          description={`${search.provider ?? "crawler"}${search.fallback_used ? " · 回退" : ""}`}
        >
          <SourceList sources={(search.results ?? []).map((item) => ({ ...item, query: keyword }))} />
        </GlassCard>
      )}

      {research && (
        <GlassCard
          title="研究汇总"
          description={research.summary ?? `${(research.sources ?? []).length} 条来源`}
        >
          <div className="mb-3 flex flex-wrap gap-2">
            <Badge tone={research.fallback_used ? "amber" : "green"}>
              {research.fallback_used ? "含回退" : "真实检索"}
            </Badge>
            <Badge tone="cyan">{research.provider ?? "crawler"}</Badge>
          </div>
          <SourceList sources={research.sources ?? []} />
        </GlassCard>
      )}
    </div>
  );
}

function SourceList({ sources }: { sources: Record<string, unknown>[] }) {
  return (
    <div className="grid gap-2">
      {sources.slice(0, 20).map((source, index) => (
        <article key={index} className="glass-soft p-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm font-bold text-white">{String(source.title ?? "未命名来源")}</p>
              {source.query ? <p className="mt-0.5 text-[11px] text-slate-500">查询：{String(source.query)}</p> : null}
            </div>
            {String(source.source ?? "").toLowerCase() === "mock" && (
              <Badge tone="amber">模拟</Badge>
            )}
            {source.link ? (
              <a
                href={String(source.link)}
                target="_blank"
                rel="noreferrer"
                className="focus-ring shrink-0 rounded-lg p-1.5 text-slate-400 hover:text-accent"
                aria-label="打开来源"
              >
                <ExternalLink className="h-4 w-4" />
              </a>
            ) : null}
          </div>
          {source.snippet ? (
            <p className="mt-1.5 line-clamp-3 text-xs leading-5 text-slate-400">{String(source.snippet)}</p>
          ) : null}
        </article>
      ))}
      {!sources.length && <p className="text-xs text-slate-500">暂无来源</p>}
    </div>
  );
}
