import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FlaskConical, KeyRound, Radio, Save } from "lucide-react";
import { IS_OFFLINE } from "@/shared/api/offline";
import {
  useAiConfig,
  useSaveAiConfig,
  useTestAiConnection,
  useTestSearchConnection,
} from "@/shared/api/hooks";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";

const STORAGE_KEY = "yuanfan-ai-config";

interface AiPreset {
  id: string;
  label: string;
  group: string;
  baseUrl: string;
  model: string;
  models: string[];
}

const AI_PRESETS: AiPreset[] = [
  {
    id: "deepseek",
    label: "DeepSeek",
    group: "国内主流",
    baseUrl: "https://api.deepseek.com/v1",
    model: "deepseek-chat",
    models: ["deepseek-chat", "deepseek-reasoner", "deepseek-v4-flash"],
  },
  {
    id: "qwen",
    label: "阿里云百炼 Qwen",
    group: "国内主流",
    baseUrl: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    model: "qwen-plus",
    models: ["qwen-max", "qwen-plus", "qwen-turbo", "qwen-long"],
  },
  {
    id: "kimi",
    label: "Kimi（Moonshot）",
    group: "国内主流",
    baseUrl: "https://api.moonshot.cn/v1",
    model: "kimi-k2-0711-preview",
    models: [
      "kimi-k2-0711-preview",
      "moonshot-v1-8k",
      "moonshot-v1-32k",
      "moonshot-v1-128k",
    ],
  },
  {
    id: "glm",
    label: "智谱 GLM",
    group: "国内主流",
    baseUrl: "https://open.bigmodel.cn/api/paas/v4",
    model: "glm-4-flash",
    models: ["glm-4-flash", "glm-4-plus", "glm-4-air", "glm-4-long"],
  },
  {
    id: "doubao",
    label: "火山方舟 Doubao",
    group: "国内主流",
    baseUrl: "https://ark.cn-beijing.volces.com/api/v3",
    model: "doubao-pro-32k",
    models: [
      "doubao-pro-32k",
      "doubao-pro-128k",
      "doubao-1-5-pro-32k-250115",
      "doubao-seed-1-6-250615",
    ],
  },
  {
    id: "baidu",
    label: "百度千帆 ERNIE",
    group: "国内主流",
    baseUrl: "https://qianfan.baidubce.com/v2",
    model: "ernie-4.0-8k",
    models: ["ernie-4.0-8k", "ernie-4.0-turbo-8k", "ernie-3.5-8k"],
  },
  {
    id: "hunyuan",
    label: "腾讯混元 Hunyuan",
    group: "国内主流",
    baseUrl: "https://api.hunyuan.cloud.tencent.com/v1",
    model: "hunyuan-turbos-latest",
    models: [
      "hunyuan-turbos-latest",
      "hunyuan-turbo-latest",
      "hunyuan-standard",
      "hunyuan-lite",
    ],
  },
  {
    id: "minimax",
    label: "MiniMax",
    group: "国内主流",
    baseUrl: "https://api.minimaxi.com/v1",
    model: "MiniMax-Text-01",
    models: ["MiniMax-Text-01", "abab6.5s-chat", "abab6.5g-chat"],
  },
  {
    id: "yi",
    label: "零一万物 Yi",
    group: "国内主流",
    baseUrl: "https://api.lingyiwanwu.com/v1",
    model: "yi-lightning",
    models: ["yi-lightning", "yi-large", "yi-medium"],
  },
  {
    id: "stepfun",
    label: "阶跃星辰 StepFun",
    group: "国内主流",
    baseUrl: "https://api.stepfun.com/v1",
    model: "step-2-16k",
    models: ["step-2-16k", "step-1-8k", "step-1-32k"],
  },
  {
    id: "baichuan",
    label: "百川智能 Baichuan",
    group: "国内主流",
    baseUrl: "https://api.baichuan-ai.com/v1",
    model: "Baichuan4-Turbo",
    models: ["Baichuan4-Turbo", "Baichuan4", "Baichuan3-Turbo"],
  },
  {
    id: "spark",
    label: "讯飞星火 Spark",
    group: "国内主流",
    baseUrl: "https://spark-api-open.xf-yun.com/v1",
    model: "generalv3.5",
    models: ["generalv3.5", "4.0Ultra", "generalv3", "lite"],
  },
  {
    id: "siliconflow",
    label: "硅基流动 SiliconFlow",
    group: "国内主流",
    baseUrl: "https://api.siliconflow.cn/v1",
    model: "deepseek-ai/DeepSeek-V3",
    models: [
      "deepseek-ai/DeepSeek-V3",
      "Qwen/Qwen2.5-72B-Instruct",
      "THUDM/glm-4-9b-chat",
      "meta-llama/Meta-Llama-3.1-8B-Instruct",
    ],
  },
  {
    id: "openai",
    label: "OpenAI",
    group: "国际主流",
    baseUrl: "https://api.openai.com/v1",
    model: "gpt-4o-mini",
    models: ["gpt-5", "gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini"],
  },
  {
    id: "anthropic",
    label: "Anthropic Claude",
    group: "国际主流",
    baseUrl: "https://api.anthropic.com/v1",
    model: "claude-sonnet-4-20250514",
    models: [
      "claude-sonnet-4-20250514",
      "claude-3-5-sonnet-latest",
      "claude-3-5-haiku-latest",
      "claude-3-opus-latest",
    ],
  },
  {
    id: "gemini",
    label: "Google Gemini",
    group: "国际主流",
    baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai",
    model: "gemini-2.5-flash",
    models: ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-1.5-pro"],
  },
  {
    id: "groq",
    label: "Groq",
    group: "国际主流",
    baseUrl: "https://api.groq.com/openai/v1",
    model: "llama-3.3-70b-versatile",
    models: ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
  },
  {
    id: "mistral",
    label: "Mistral AI",
    group: "国际主流",
    baseUrl: "https://api.mistral.ai/v1",
    model: "mistral-large-latest",
    models: [
      "mistral-large-latest",
      "mistral-medium-latest",
      "mistral-small-latest",
      "open-mistral-nemo",
    ],
  },
  {
    id: "xai",
    label: "xAI Grok",
    group: "国际主流",
    baseUrl: "https://api.x.ai/v1",
    model: "grok-2-latest",
    models: ["grok-2-latest", "grok-2-1212", "grok-beta"],
  },
  {
    id: "perplexity",
    label: "Perplexity",
    group: "国际主流",
    baseUrl: "https://api.perplexity.ai",
    model: "sonar",
    models: ["sonar", "sonar-pro", "sonar-reasoning", "sonar-deep-research"],
  },
  {
    id: "together",
    label: "Together AI",
    group: "国际主流",
    baseUrl: "https://api.together.xyz/v1",
    model: "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    models: [
      "meta-llama/Llama-3.3-70B-Instruct-Turbo",
      "meta-llama/Llama-3.1-8B-Instruct-Turbo",
      "Qwen/Qwen2.5-72B-Instruct-Turbo",
    ],
  },
  {
    id: "openrouter",
    label: "OpenRouter",
    group: "聚合与本地",
    baseUrl: "https://openrouter.ai/api/v1",
    model: "openai/gpt-4o-mini",
    models: [
      "openai/gpt-4o-mini",
      "anthropic/claude-3.5-sonnet",
      "google/gemini-2.0-flash-001",
      "deepseek/deepseek-chat",
    ],
  },
  {
    id: "ollama",
    label: "Ollama（本地）",
    group: "聚合与本地",
    baseUrl: "http://localhost:11434/v1",
    model: "llama3.1",
    models: ["llama3.1", "qwen2.5", "gemma2", "deepseek-r1"],
  },
  {
    id: "lmstudio",
    label: "LM Studio（本地）",
    group: "聚合与本地",
    baseUrl: "http://localhost:1234/v1",
    model: "local-model",
    models: ["local-model"],
  },
];

const CUSTOM_PRESET = "custom";

const BASE_URL_PATHS: Record<string, string> = {
  "api.deepseek.com": "/v1",
  "api.openai.com": "/v1",
  "api.anthropic.com": "/v1",
  "api.moonshot.cn": "/v1",
  "api.siliconflow.cn": "/v1",
  "api.x.ai": "/v1",
  "api.mistral.ai": "/v1",
  "api.together.xyz": "/v1",
  "api.groq.com": "/openai/v1",
  "generativelanguage.googleapis.com": "/v1beta/openai",
  "open.bigmodel.cn": "/api/paas/v4",
  "dashscope.aliyuncs.com": "/compatible-mode/v1",
  "ark.cn-beijing.volces.com": "/api/v3",
  "qianfan.baidubce.com": "/v2",
  "api.hunyuan.cloud.tencent.com": "/v1",
  "api.minimaxi.com": "/v1",
  "api.minimax.chat": "/v1",
  "api.lingyiwanwu.com": "/v1",
  "api.stepfun.com": "/v1",
  "api.baichuan-ai.com": "/v1",
  "spark-api-open.xf-yun.com": "/v1",
  "openrouter.ai": "/api/v1",
};

interface AiConfig {
  apiKey: string;
  baseUrl: string;
  model: string;
  preset: string;
  searchProvider: string;
  searchMaxResults: number;
  timeout: number;
  hasKey: boolean;
}

function normalizeBaseUrl(url: string): string {
  const trimmed = url.trim().replace(/\/+$/, "");
  try {
    const parsed = new URL(trimmed);
    const suffix = BASE_URL_PATHS[parsed.hostname] ?? "";
    if (suffix && (parsed.pathname === "" || parsed.pathname === "/")) {
      parsed.pathname = suffix;
      return parsed.toString().replace(/\/+$/, "");
    }
  } catch {
    // keep malformed or custom values as-is
  }
  return trimmed;
}

function resolvePreset(baseUrl: string): string {
  const normalized = normalizeBaseUrl(baseUrl);
  return (
    AI_PRESETS.find((preset) => normalizeBaseUrl(preset.baseUrl) === normalized)
      ?.id ?? CUSTOM_PRESET
  );
}

function effectivePreset(preset: string, baseUrl: string): string {
  const selected = AI_PRESETS.find((item) => item.id === preset);
  if (
    selected &&
    normalizeBaseUrl(selected.baseUrl) === normalizeBaseUrl(baseUrl)
  ) {
    return selected.id;
  }
  return resolvePreset(baseUrl);
}

function readConfig(): AiConfig {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<AiConfig>;
      const normalized: AiConfig = {
        ...defaultConfig(),
        ...parsed,
        baseUrl: normalizeBaseUrl(
          String(parsed.baseUrl ?? defaultConfig().baseUrl),
        ),
      };
      // 在线模式安全迁移：忽略并清除历史版本遗留的明文 API Key；
      // 离线单文件例外保留浏览器 Key（仅本机演示）。
      const stored: Partial<AiConfig> = { ...normalized };
      if (!IS_OFFLINE) {
        delete stored.apiKey;
      }
      const needsRewrite =
        normalized.baseUrl !== parsed.baseUrl ||
        (!IS_OFFLINE && typeof parsed.apiKey === "string" && parsed.apiKey !== "");
      if (needsRewrite) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(stored));
      }
      return normalized;
    }
  } catch {
    // ignore malformed local config
  }
  return defaultConfig();
}

function defaultConfig(): AiConfig {
  return {
    apiKey: "",
    baseUrl: "https://api.deepseek.com/v1",
    model: "deepseek-chat",
    preset: "deepseek",
    searchProvider: "crawler",
    searchMaxResults: 5,
    timeout: 120,
    hasKey: false,
  };
}

export function AiConfigPanel() {
  const queryClient = useQueryClient();
  const [local, setLocal] = useState<Partial<AiConfig>>({});
  const [saved, setSaved] = useState(false);
  const { data: backendStatus } = useAiConfig();
  const saveMutation = useSaveAiConfig();
  const aiTest = useTestAiConnection();
  const searchTest = useTestSearchConnection();

  const config = useMemo<AiConfig>(() => {
    const stored = readConfig();
    const base = IS_OFFLINE || !backendStatus ? stored : {
      ...stored,
      baseUrl: backendStatus.base_url || stored.baseUrl,
      model: backendStatus.model || stored.model,
      preset: backendStatus.preset || stored.preset,
      searchProvider: backendStatus.search_provider || stored.searchProvider,
      searchMaxResults: backendStatus.search_max_results ?? stored.searchMaxResults,
      timeout: backendStatus.timeout ?? stored.timeout,
      hasKey: Boolean(backendStatus.has_key || backendStatus.configured),
    };
    const merged = { ...base, ...local };
    return { ...merged, preset: effectivePreset(merged.preset, merged.baseUrl) };
  }, [backendStatus, local]);

  const update = (key: keyof AiConfig, value: string | number | boolean) => {
    if (key === "baseUrl") {
      setLocal((prev) => ({
        ...prev,
        baseUrl: String(value),
        preset: resolvePreset(String(value)),
      }));
    } else if (key === "model") {
      setLocal((prev) => ({
        ...prev,
        model: String(value),
        preset: effectivePreset(config.preset, config.baseUrl),
      }));
    } else {
      setLocal((prev) => ({ ...prev, [key]: value }));
    }
    setSaved(false);
  };

  const applyPreset = (preset: string) => {
    const selected = AI_PRESETS.find((item) => item.id === preset);
    if (!selected) {
      setLocal((prev) => ({ ...prev, preset: CUSTOM_PRESET }));
    } else {
      setLocal((prev) => ({
        ...prev,
        preset: selected.id,
        baseUrl: selected.baseUrl,
        model: selected.model,
      }));
    }
    setSaved(false);
  };

  const save = async () => {
    const merged = { ...config, ...local };
    const next = { ...merged, baseUrl: normalizeBaseUrl(String(merged.baseUrl)) };
    if (IS_OFFLINE) {
      // 离线单文件没有后端，浏览器直连必须由前端持有 Key，属于本机演示的例外
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } else {
      // 在线模式：Key 只交给后端内存，不落 localStorage（防同源 XSS 窃取明文）
      const stored: Record<string, unknown> = { ...next };
      delete stored.apiKey;
      localStorage.setItem(STORAGE_KEY, JSON.stringify(stored));
      await saveMutation.mutateAsync({
        api_key: next.apiKey || undefined,
        base_url: next.baseUrl,
        model: next.model,
        preset: next.preset,
        search_provider: next.searchProvider,
        search_max_results: next.searchMaxResults,
        timeout: next.timeout,
      });
      await queryClient.invalidateQueries({ queryKey: ["ai-config"] });
    }
    setSaved(true);
    window.setTimeout(() => setSaved(false), 2500);
  };

  const runSearchTest = () => {
    searchTest.mutate({
      query: "跨境电商 最新趋势",
      search_provider: config.searchProvider,
      search_max_results: config.searchMaxResults,
      timeout: config.timeout,
    });
  };

  const runAiTest = () => {
    aiTest.mutate({
      api_key: config.apiKey || undefined,
      base_url: config.baseUrl,
      model: config.model,
      timeout: config.timeout,
    });
  };

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-2">
        {!IS_OFFLINE && backendStatus && (
          <Badge tone={backendStatus.configured ? "green" : "amber"}>
            {backendStatus.configured
              ? "后端已配置"
              : "后端未配置（需 API Key + 模型）"}
          </Badge>
        )}
        <Badge tone={config.hasKey ? "green" : "neutral"}>
          {config.hasKey
            ? IS_OFFLINE
              ? "Key 已保存在浏览器本地"
              : "后端内存已配置 Key"
            : IS_OFFLINE
              ? "浏览器 Key 未保存"
              : "后端内存未配置 Key"}
        </Badge>
        {!IS_OFFLINE && backendStatus && !backendStatus.configured && (
          <p className="w-full text-xs text-amber-200/80">
            请在 API Key 栏填写（模型默认 DeepSeek，可按需切换提供商）后点击“保存配置”，
            后端内存配置成功后这里会变为“后端已配置”。
          </p>
        )}
      </div>
      <Field label="API Key">
        <input
          type="password"
          value={config.apiKey}
          onChange={(event) => update("apiKey", event.target.value)}
          placeholder={config.hasKey ? "已配置，留空沿用后端 Key" : "sk-..."}
          className="glass-inset focus-ring h-10 w-full px-3 text-sm text-slate-100 placeholder:text-slate-600"
        />
      </Field>
      <Field label="提供商">
        <select
          value={config.preset}
          onChange={(event) => applyPreset(event.target.value)}
          className="glass-inset focus-ring h-10 w-full px-3 text-sm text-slate-100"
        >
          {["国内主流", "国际主流", "聚合与本地"].map((group) => (
            <optgroup key={group} label={group}>
              {AI_PRESETS.filter((preset) => preset.group === group).map((preset) => (
                <option key={preset.id} value={preset.id}>
                  {preset.label}
                </option>
              ))}
            </optgroup>
          ))}
          <option value={CUSTOM_PRESET}>自定义</option>
        </select>
      </Field>
      <Field label="Base URL">
        <input
          type="text"
          value={config.baseUrl}
          onChange={(event) => update("baseUrl", event.target.value)}
          placeholder="https://api.deepseek.com/v1"
          className="glass-inset focus-ring h-10 w-full px-3 text-sm text-slate-100"
        />
      </Field>
      <Field label="模型">
        <input
          type="text"
          value={config.model}
          onChange={(event) => update("model", event.target.value)}
          placeholder="deepseek-chat"
          list="ai-model-suggestions"
          className="glass-inset focus-ring h-10 w-full px-3 text-sm text-slate-100"
        />
        <datalist id="ai-model-suggestions">
          {AI_PRESETS.find((preset) => preset.id === config.preset)?.models.map(
            (model) => (
              <option key={model} value={model} />
            ),
          )}
        </datalist>
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="搜索服务">
          <select
            value={config.searchProvider}
            onChange={(event) => update("searchProvider", event.target.value)}
            className="glass-inset focus-ring h-10 w-full px-3 text-sm text-slate-100"
          >
            <option value="crawler">crawler（Wikimedia）</option>
            <option value="duckduckgo_html">duckduckgo_html</option>
            <option value="mock">mock（离线回退）</option>
          </select>
        </Field>
        <Field label="搜索条数">
          <input
            type="number"
            min={1}
            max={20}
            value={config.searchMaxResults}
            onChange={(event) => update("searchMaxResults", Number(event.target.value))}
            className="glass-inset focus-ring h-10 w-full px-3 text-sm text-slate-100"
          />
        </Field>
      </div>
      <Field label="超时秒数">
        <input
          type="number"
          min={1}
          max={600}
          value={config.timeout}
          onChange={(event) => update("timeout", Number(event.target.value))}
          className="glass-inset focus-ring h-10 w-full px-3 text-sm text-slate-100"
        />
      </Field>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="flex items-center gap-2 text-xs text-slate-500">
          <KeyRound className="h-4 w-4" />
          {IS_OFFLINE
            ? "离线单文件：Key 保存在浏览器本地（仅本机演示，勿填真实付费 Key）"
            : "在线模式：Key 仅存后端内存并永不回传，不写入浏览器存储"}
        </p>
        <Button size="sm" onClick={save} disabled={saveMutation.isPending}>
          {saved ? <CheckCircle2 className="h-4 w-4" /> : <Save className="h-4 w-4" />}
          {saved ? "已保存" : saveMutation.isPending ? "保存中..." : "保存配置"}
        </Button>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Button
          variant="secondary"
          size="sm"
          disabled={IS_OFFLINE || aiTest.isPending}
          onClick={runAiTest}
        >
          <FlaskConical className="h-4 w-4" />
          {aiTest.isPending ? "测试中..." : "测试 AI"}
        </Button>
        <Button
          variant="secondary"
          size="sm"
          disabled={IS_OFFLINE || searchTest.isPending}
          onClick={runSearchTest}
        >
          <Radio className="h-4 w-4" />
          {searchTest.isPending ? "测试中..." : "测试搜索"}
        </Button>
      </div>
      {(aiTest.data || searchTest.data) && (
        <div className="glass-inset grid gap-2 p-3 text-xs text-slate-300">
          {aiTest.data && <p>AI：{formatTestResult(aiTest.data)}</p>}
          {searchTest.data && <p>搜索：{formatTestResult(searchTest.data)}</p>}
        </div>
      )}
      {searchTest.isError && (
        <p className="text-xs text-red-300">
          搜索：{searchTest.error instanceof Error ? searchTest.error.message : "搜索测试失败"}
        </p>
      )}
      {saveMutation.isError && (
        <p className="text-xs text-red-300">
          {saveMutation.error instanceof Error ? saveMutation.error.message : "配置保存失败"}
        </p>
      )}
    </div>
  );
}

function formatTestResult(result: Record<string, unknown>): string {
  if (result.ok === true) {
    const results = Array.isArray(result.results) ? result.results.length : null;
    const detail =
      results != null
        ? `${results} 条结果`
        : `${String(result.latency_ms ?? "-")}ms`;
    return `连接成功（${String(result.provider ?? "default")}，${detail}）`;
  }
  const raw = String(result.error ?? result.message ?? "连接失败");
  if (/OPENAI_API_KEY|not configured|AI 未配置|缺少 API Key/.test(raw)) {
    return "AI 未配置：请先填写 API Key 与模型并保存配置，再点击“测试 AI”";
  }
  return raw;
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="grid gap-1.5">
      <span className="text-xs font-semibold text-slate-400">{label}</span>
      {children}
    </label>
  );
}
