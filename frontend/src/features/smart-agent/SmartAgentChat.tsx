import { useEffect, useRef, useState } from "react";
import { Eraser, LogOut, Send, ShieldAlert, Square } from "lucide-react";
import { Button } from "@/shared/ui/button";
import { GlassCard } from "@/shared/ui/glass-card";
import { IS_OFFLINE } from "@/shared/api/offline";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

interface ToolRun {
  id: string;
  tool: string;
  args: string;
  preview: string;
  ok: boolean;
}

interface SseEvent {
  event: string;
  data?: Record<string, unknown>;
}

function parseSseBlock(raw: string): SseEvent | null {
  let event = "";
  let dataText = "";
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) dataText += line.slice(5).trim();
  }
  if (!dataText) return null;
  try {
    return { event, data: JSON.parse(dataText) as Record<string, unknown> };
  } catch {
    return null;
  }
}

function nextId() {
  return `msg-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function SmartAgentChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [toolRuns, setToolRuns] = useState<ToolRun[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [authed, setAuthed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const readerRef = useRef<ReadableStreamDefaultReader<Uint8Array> | null>(null);
  const cancelledRef = useRef(false);

  const goLogin = () => {
    localStorage.removeItem("smart_agent_token");
    localStorage.removeItem("smart_agent_username");
    window.location.replace("/agent/login.html");
  };

  useEffect(() => {
    if (IS_OFFLINE) return;
    let cancelled = false;
    cancelledRef.current = false;
    const token = localStorage.getItem("smart_agent_token");
    if (!token) {
      goLogin();
      return;
    }
    fetch("/agent/api/me", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((response) => {
        if (response.status === 401) {
          goLogin();
          return null;
        }
        if (!response.ok) throw new Error("小助手后端连接失败");
        return response.json();
      })
      .then(() => {
        if (!cancelled) setAuthed(true);
      })
      .catch(() => {
        if (!cancelled) setError("无法连接小助手后端，请确认服务已启动");
      });
    return () => {
      cancelled = true;
      cancelledRef.current = true;
      readerRef.current?.cancel().catch(() => undefined);
    };
  }, []);

  const handleEvent = (
    event: SseEvent,
    assistantId: { current: string },
  ) => {
    if (event.event === "tool") {
      setToolRuns((prev) => [
        {
          id: nextId(),
          tool: String(event.data?.tool ?? "get_market_info"),
          args: JSON.stringify(event.data?.args ?? {}),
          preview: String(event.data?.result_preview ?? ""),
          ok: event.data?.ok !== false,
        },
        ...prev,
      ]);
    } else if (event.event === "delta") {
      const content = String(event.data?.content ?? "");
      if (!content) return;
      if (!assistantId.current) assistantId.current = nextId();
      setMessages((prev) => {
        const next = [...prev];
        const index = next.findIndex((item) => item.id === assistantId.current);
        if (index === -1) {
          next.push({ id: assistantId.current, role: "assistant", content });
        } else {
          next[index] = {
            ...next[index],
            content: next[index].content + content,
          };
        }
        return next;
      });
    } else if (event.event === "error") {
      setError(String(event.data?.message ?? "小助手执行失败"));
    }
  };

  const send = async () => {
    const text = draft.trim();
    if (!text || busy || !authed) return;
    const token = localStorage.getItem("smart_agent_token");
    if (!token) {
      goLogin();
      return;
    }
    setDraft("");
    setError(null);
    setBusy(true);
    setMessages((prev) => [
      ...prev,
      { id: nextId(), role: "user", content: text },
    ]);
    const assistantId = { current: "" };
    try {
      const response = await fetch("/agent/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ message: text }),
      });
      if (response.status === 401) {
        goLogin();
        return;
      }
      if (!response.ok) {
        let detail = `请求失败 (${response.status})`;
        try {
          const payload = (await response.json()) as { detail?: unknown };
          if (payload.detail) {
            detail =
              typeof payload.detail === "string"
                ? payload.detail
                : JSON.stringify(payload.detail);
          }
        } catch {
          // 保留默认错误信息
        }
        setError(detail);
        return;
      }
      if (!response.body) throw new Error("浏览器不支持流式响应");
      const reader = response.body.getReader();
      readerRef.current = reader;
      const decoder = new TextDecoder();
      let buffer = "";
      while (!cancelledRef.current) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let index;
        while ((index = buffer.indexOf("\n\n")) !== -1) {
          const raw = buffer.slice(0, index);
          buffer = buffer.slice(index + 2);
          const parsed = parseSseBlock(raw);
          if (parsed) handleEvent(parsed, assistantId);
        }
      }
      if (buffer.trim()) {
        const parsed = parseSseBlock(buffer);
        if (parsed) handleEvent(parsed, assistantId);
      }
    } catch (err) {
      if (!cancelledRef.current) {
        setError(err instanceof Error ? err.message : "小助手请求失败");
      }
    } finally {
      readerRef.current = null;
      if (!cancelledRef.current) setBusy(false);
    }
  };

  const cancel = async () => {
    await readerRef.current?.cancel();
    readerRef.current = null;
    setBusy(false);
  };

  const clear = () => {
    setMessages([]);
    setToolRuns([]);
    setError(null);
  };

  if (IS_OFFLINE) {
    return (
      <GlassCard>
        <p className="text-sm text-slate-400">
          小助手需要在线后端，离线模式不可用。
        </p>
      </GlassCard>
    );
  }

  if (!authed) {
    return (
      <GlassCard>
        <p className="text-sm text-slate-400">正在校验登录状态...</p>
      </GlassCard>
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px] lg:items-start">
      <GlassCard
        title="小助手"
        description="DeepSeek 工具调用对话"
        action={
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={clear}
              disabled={busy}
            >
              <Eraser className="h-4 w-4" />
              清空
            </Button>
            {busy && (
              <Button variant="danger" size="sm" onClick={cancel}>
                <Square className="h-4 w-4" />
                停止
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={goLogin}>
              <LogOut className="h-4 w-4" />
              退出登录
            </Button>
          </div>
        }
      >
        <div className="grid min-h-[420px] gap-3">
          <div className="glass-inset grid max-h-[460px] gap-3 overflow-y-auto p-3">
            {messages.length === 0 && (
              <p className="p-6 text-center text-xs text-slate-500">
                输入问题开始对话
              </p>
            )}
            {messages.map((message) => (
              <div
                key={message.id}
                className={
                  message.role === "user"
                    ? "ml-auto max-w-[88%] rounded-lg bg-accent/10 px-3 py-2 text-sm text-slate-100"
                    : "max-w-[92%] rounded-lg bg-white/5 px-3 py-2 text-sm leading-6 text-slate-100 whitespace-pre-wrap"
                }
              >
                {message.content}
              </div>
            ))}
            {busy && messages[messages.length - 1]?.role === "user" && (
              <p className="text-xs text-slate-500">小助手正在执行...</p>
            )}
          </div>

          {error && (
            <div className="flex items-start gap-2 rounded-lg border border-red-400/30 bg-red-500/10 p-3 text-xs text-red-200">
              <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void send();
                }
              }}
              rows={3}
              placeholder="输入问题..."
              disabled={busy}
              className="glass-inset focus-ring h-20 w-full resize-none px-3 py-2 text-sm text-slate-100"
            />
            <Button onClick={send} disabled={busy || !draft.trim()}>
              <Send className="h-4 w-4" />
              发送
            </Button>
          </div>
        </div>
      </GlassCard>

      <GlassCard
        title="工具执行"
        description="工具调用记录"
        action={
          <span className="font-mono text-xs text-accent">
            {toolRuns.length} 步
          </span>
        }
      >
        <div className="grid max-h-[540px] gap-3 overflow-y-auto pr-1">
          {toolRuns.length === 0 && (
            <p className="text-xs text-slate-500">暂无工具调用</p>
          )}
          {toolRuns.map((run) => (
            <article key={run.id} className="glass-soft p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="font-mono text-xs font-bold text-accent">
                  {run.tool}
                </p>
                <span
                  className={
                    run.ok
                      ? "text-[11px] text-emerald-300"
                      : "text-[11px] text-red-300"
                  }
                >
                  {run.ok ? "ok" : "error"}
                </span>
              </div>
              <p className="mt-2 font-mono text-[11px] text-slate-500">
                {run.args}
              </p>
              <p className="mt-2 line-clamp-5 text-xs leading-5 text-slate-400">
                {run.preview}
              </p>
            </article>
          ))}
        </div>
      </GlassCard>
    </div>
  );
}
