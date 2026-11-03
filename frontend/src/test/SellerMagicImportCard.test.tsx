import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { SellerMagicImportCard } from "@/features/workbench/SellerMagicImportCard";
import type { SellerMagicImportResult } from "@/shared/api/types";

const mocks = vi.hoisted(() => ({
  transitionNavigate: vi.fn(),
  mutateAsync: vi.fn(),
}));

const importResult: SellerMagicImportResult = {
  ok: true,
  mapping: {
    matched: { 关键词: "keyword" },
    unmatched: [],
    missing: [],
    dropped: 0,
    numeric_columns: ["search_index", "price_median"],
  },
  summary: {
    rows: 5,
    matched_columns: 1,
    unmatched_columns: [],
    numeric_columns: ["search_index", "price_median"],
    dropped_rows: 0,
    keyword_count: 4,
    avg_price: 21.5,
  },
  top_keywords: [{ keyword: "pet feeder", avg_price: 25.5 }],
  file: "seller_export.csv",
};

vi.mock("@/shared/api/hooks", () => ({
  useSellerMagicImport: () => ({
    isPending: false,
    mutateAsync: mocks.mutateAsync,
  }),
}));

vi.mock("@/shared/api/offline", () => ({ IS_OFFLINE: false }));
vi.mock("@/widgets/RouteTransition", () => ({
  useTransitionNavigate: () => mocks.transitionNavigate,
}));

describe("SellerMagicImportCard（卖家精灵 CSV 导入）", () => {
  it("上传后展示映射摘要与可分析关键词", async () => {
    mocks.mutateAsync.mockResolvedValue(importResult);
    const user = userEvent.setup();
    render(<SellerMagicImportCard />);

    const file = new File(["关键词,平均价格\npet feeder,25.5"], "seller_export.csv", {
      type: "text/csv",
    });
    await user.upload(screen.getByLabelText(/选择 CSV 文件/), file);
    await user.click(screen.getByRole("button", { name: "上传并映射" }));

    expect(mocks.mutateAsync).toHaveBeenCalledWith(file);
    expect(await screen.findByText("有效行数")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("$21.50")).toBeInTheDocument();
    expect(screen.getByText("pet feeder")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /去四脑分析/ })).toBeInTheDocument();
  });
});
