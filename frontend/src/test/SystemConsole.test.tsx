import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { JobsPanel } from "@/features/system/JobsPanel";
import { AiConfigPanel } from "@/features/ai-config/AiConfigPanel";

let mockSavePayloads: Array<Record<string, unknown>> = [];
let mockSearchPayloads: Array<Record<string, unknown>> = [];
let mockAiPayloads: Array<Record<string, unknown>> = [];

vi.mock("@/shared/api/hooks", () => ({
  useJobs: () => ({
    data: {
      count: 1,
      items: [
        {
          name: "daily_update",
          label: "每日数据更新",
          status: "running",
          progress: { stage: "3/7", message: "联网检索中" },
        },
      ],
    },
  }),
  useStartJob: () => ({ isPending: false, mutate: vi.fn() }),
  useStopJob: () => ({ isPending: false, mutate: vi.fn() }),
  useAiConfig: () => ({
    data: {
      configured: true,
      model: "deepseek-chat",
      base_url: "https://api.deepseek.com/v1",
      preset: "deepseek",
    },
  }),
  useSaveAiConfig: () => ({
    isPending: false,
    isError: false,
    mutateAsync: async (payload: Record<string, unknown>) => {
      mockSavePayloads.push(payload);
    },
    error: null,
  }),
  useTestAiConnection: () => ({
    isPending: false,
    mutate: (payload: Record<string, unknown>) => {
      mockAiPayloads.push(payload);
    },
    data: null,
  }),
  useTestSearchConnection: () => ({
    isPending: false,
    mutate: (payload: Record<string, unknown>) => {
      mockSearchPayloads.push(payload);
    },
    data: null,
    isError: false,
    error: null,
  }),
}));

describe("system console panels", () => {
  beforeEach(() => {
    mockSavePayloads = [];
    mockSearchPayloads = [];
    mockAiPayloads = [];
    localStorage.clear();
  });

  it("shows a running job with progress and stop control", () => {
    render(<JobsPanel />);
    expect(screen.getByText("每日数据更新")).toBeInTheDocument();
    expect(screen.getByText("running")).toBeInTheDocument();
    expect(screen.getByText("联网检索中")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /停止/ })).toBeInTheDocument();
  });

  it("saves AI config to backend without persisting the raw API key", async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <AiConfigPanel />
      </QueryClientProvider>,
    );
    const keyInput = screen.getByLabelText("API Key");
    await user.clear(keyInput);
    await user.type(keyInput, "sk-test-123");
    const model = screen.getByLabelText("模型");
    await user.clear(model);
    await user.type(model, "gpt-5");
    await user.click(screen.getByRole("button", { name: "保存配置" }));
    // 在线模式：模型等非敏感配置可缓存，但明文 Key 不得落盘
    const stored = localStorage.getItem("yuanfan-ai-config") ?? "";
    expect(stored).toContain("gpt-5");
    expect(stored).not.toContain("sk-test-123");
    // Key 仍然随请求传给后端内存
    expect(mockSavePayloads[0]).toMatchObject({ api_key: "sk-test-123" });
  });

  it("fills Base URL and model from a provider preset and saves it", async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <AiConfigPanel />
      </QueryClientProvider>,
    );
    await user.selectOptions(screen.getByLabelText("提供商"), "qwen");
    expect(screen.getByLabelText("Base URL")).toHaveValue(
      "https://dashscope.aliyuncs.com/compatible-mode/v1",
    );
    expect(screen.getByLabelText("模型")).toHaveValue("qwen-plus");
    await user.click(screen.getByRole("button", { name: "保存配置" }));
    expect(mockSavePayloads[0]).toMatchObject({
      preset: "qwen",
      base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1",
      model: "qwen-plus",
    });
    expect(localStorage.getItem("yuanfan-ai-config")).toContain("qwen-plus");
  });

  it("supports international and local provider presets", async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <AiConfigPanel />
      </QueryClientProvider>,
    );
    await user.selectOptions(screen.getByLabelText("提供商"), "anthropic");
    expect(screen.getByLabelText("Base URL")).toHaveValue("https://api.anthropic.com/v1");
    expect(screen.getByLabelText("模型")).toHaveValue("claude-sonnet-4-20250514");
    await user.selectOptions(screen.getByLabelText("提供商"), "gemini");
    expect(screen.getByLabelText("Base URL")).toHaveValue(
      "https://generativelanguage.googleapis.com/v1beta/openai",
    );
    expect(screen.getByLabelText("模型")).toHaveValue("gemini-2.5-flash");
    await user.selectOptions(screen.getByLabelText("提供商"), "ollama");
    expect(screen.getByLabelText("Base URL")).toHaveValue("http://localhost:11434/v1");
    expect(screen.getByLabelText("模型")).toHaveValue("llama3.1");
  });

  it("keeps a custom base URL as custom preset", async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <AiConfigPanel />
      </QueryClientProvider>,
    );
    const baseUrl = screen.getByLabelText("Base URL");
    await user.clear(baseUrl);
    await user.type(baseUrl, "https://example.com/v1");
    expect(screen.getByLabelText("提供商")).toHaveValue("custom");
  });

  it("tests AI with the current form values before saving", async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <AiConfigPanel />
      </QueryClientProvider>,
    );
    await user.type(screen.getByLabelText("API Key"), "sk-form-test");
    await user.selectOptions(screen.getByLabelText("提供商"), "anthropic");
    await user.click(screen.getByRole("button", { name: "测试 AI" }));
    expect(mockAiPayloads[0]).toMatchObject({
      api_key: "sk-form-test",
      base_url: "https://api.anthropic.com/v1",
      model: "claude-sonnet-4-20250514",
    });
  });

  it("normalizes a stored legacy DeepSeek base URL on load", () => {
    localStorage.setItem(
      "yuanfan-ai-config",
      JSON.stringify({
        baseUrl: "https://api.deepseek.com",
        model: "deepseek-v4-flash",
        preset: "custom",
        timeout: 45,
        hasKey: true,
      }),
    );
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <AiConfigPanel />
      </QueryClientProvider>,
    );
    const stored = JSON.parse(localStorage.getItem("yuanfan-ai-config") ?? "{}");
    expect(stored.baseUrl).toBe("https://api.deepseek.com/v1");
    expect(stored.model).toBe("deepseek-v4-flash");
  });

  it("sends a default query and current search settings when testing search", async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <AiConfigPanel />
      </QueryClientProvider>,
    );
    await user.click(screen.getByRole("button", { name: "测试搜索" }));
    expect(mockSearchPayloads[0]).toMatchObject({
      query: "跨境电商 最新趋势",
      search_provider: "crawler",
      search_max_results: 5,
    });
  });
});
