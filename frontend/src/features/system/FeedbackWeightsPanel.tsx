import { useState } from "react";
import type { FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Send, SlidersHorizontal } from "lucide-react";
import {
  useFeedbackList,
  usePostFeedback,
  useSaveScoringWeights,
  useScoringWeights,
} from "@/shared/api/hooks";
import { IS_OFFLINE } from "@/shared/api/offline";
import { Button } from "@/shared/ui/button";
import { GlassCard } from "@/shared/ui/glass-card";

export function FeedbackWeightsPanel() {
  const queryClient = useQueryClient();
  const feedback = useFeedbackList();
  const weights = useScoringWeights();
  const post = usePostFeedback();
  const saveWeights = useSaveScoringWeights();
  const [content, setContent] = useState("");
  const [rating, setRating] = useState(5);
  const [category, setCategory] = useState("");
  const [weightDraft, setWeightDraft] = useState<Record<string, number>>({});

  if (IS_OFFLINE) {
    return (
      <GlassCard>
        <p className="text-sm text-slate-400">反馈与评分权重面板需要在线后端，离线模式不可用。</p>
      </GlassCard>
    );
  }

  const submitFeedback = async (event: FormEvent) => {
    event.preventDefault();
    if (!content.trim()) return;
    await post.mutateAsync({ content: content.trim(), rating, category: category || undefined });
    setContent("");
    setCategory("");
    await queryClient.invalidateQueries({ queryKey: ["feedback"] });
  };

  const saveWeightsNow = async () => {
    await saveWeights.mutateAsync(weightDraft);
    await queryClient.invalidateQueries({ queryKey: ["scoring-weights"] });
  };

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <GlassCard title="提交反馈" description="用于迭代评分与推荐逻辑">
        <form className="grid gap-4" onSubmit={submitFeedback}>
          <label className="grid gap-1.5">
            <span className="text-xs font-semibold text-slate-400">反馈内容</span>
            <textarea
              rows={4}
              value={content}
              onChange={(event) => setContent(event.target.value)}
              className="glass-inset focus-ring w-full resize-y px-3 py-2.5 text-sm leading-6 text-slate-200"
              placeholder="例如：推荐结果没有考虑汇率波动..."
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="grid gap-1.5">
              <span className="text-xs font-semibold text-slate-400">评分</span>
              <input
                type="number"
                min={1}
                max={5}
                value={rating}
                onChange={(event) => setRating(Number(event.target.value))}
                className="glass-inset focus-ring h-10 w-full px-3 text-sm text-slate-200"
              />
            </label>
            <label className="grid gap-1.5">
              <span className="text-xs font-semibold text-slate-400">分类</span>
              <input
                value={category}
                onChange={(event) => setCategory(event.target.value)}
                className="glass-inset focus-ring h-10 w-full px-3 text-sm text-slate-200"
                placeholder="选品 / 贸易 / 预测"
              />
            </label>
          </div>
          <Button type="submit" disabled={post.isPending || !content.trim()}>
            <Send className="h-4 w-4" />
            {post.isPending ? "提交中..." : "提交反馈"}
          </Button>
        </form>

        <div className="mt-5">
          <p className="mb-2 text-xs font-semibold text-slate-400">最近反馈</p>
          <div className="scrollbar-thin max-h-72 space-y-2 overflow-y-auto">
            {(feedback.data?.items ?? []).slice(0, 20).map((item) => (
              <div key={String(item.id ?? item.created_at ?? item.content)} className="glass-soft p-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs text-accent">评分 {item.rating ?? "-"}/5</span>
                  <span className="font-mono text-[10px] text-slate-500">{String(item.created_at ?? "").slice(0, 16)}</span>
                </div>
                <p className="mt-1 text-sm text-slate-300">{String(item.content ?? "")}</p>
              </div>
            ))}
            {!feedback.data?.items?.length && <p className="text-xs text-slate-500">暂无反馈</p>}
          </div>
        </div>
      </GlassCard>

      <GlassCard title="评分权重" description="六维评分权重实时持久化到后端 SQLite">
        <div className="grid gap-3">
          {Object.entries(weights.data ?? {}).map(([key, value]) => {
            const draftValue = weightDraft[key] ?? value;
            return (
              <label key={key} className="grid grid-cols-[1fr_auto] items-center gap-3">
                <span className="text-xs font-semibold text-slate-400">{key}</span>
                <input
                  type="number"
                  step={0.01}
                  min={0}
                  max={100}
                  value={draftValue}
                  onChange={(event) =>
                    setWeightDraft((prev) => ({ ...prev, [key]: Number(event.target.value) }))
                  }
                  className="glass-inset focus-ring h-9 w-24 px-3 text-right text-sm text-slate-200"
                />
              </label>
            );
          })}
          {!Object.keys(weights.data ?? {}).length && (
            <p className="text-xs text-slate-500">暂无权重配置，可先保存一份默认值。</p>
          )}
          <Button
            className="w-fit"
            disabled={saveWeights.isPending || !Object.keys(weightDraft).length}
            onClick={saveWeightsNow}
          >
            <SlidersHorizontal className="h-4 w-4" />
            {saveWeights.isPending ? "保存中..." : "保存权重"}
          </Button>
        </div>
      </GlassCard>
    </div>
  );
}
