import { cn } from "@/shared/lib/utils";

interface FourQuestionsMarkProps {
  size?: number;
  className?: string;
  labelClassName?: string;
}

/**
 * 远帆智品品牌图形：罗盘四问。
 * 四个节点分别对应“卖什么 / 怎么卖 / 卖到哪 / 是否值得卖”。
 */
export function FourQuestionsMark({
  size = 44,
  className,
  labelClassName,
}: FourQuestionsMarkProps) {
  return (
    <svg
      viewBox="0 0 48 48"
      width={size}
      height={size}
      role="img"
      aria-label="远帆智品 · 罗盘四问"
      className={cn("shrink-0", className)}
    >
      <circle cx="24" cy="24" r="20" fill="none" stroke="rgba(34,211,238,.34)" strokeWidth="1.2" />
      <circle cx="24" cy="24" r="14" fill="none" stroke="rgba(148,163,184,.22)" strokeWidth="0.8" strokeDasharray="2 3" />
      <path
        d="M24 4v7M24 37v7M4 24h7M37 24h7"
        stroke="rgba(148,163,184,.38)"
        strokeWidth="1"
      />
      <g strokeWidth="2" strokeLinecap="round">
        <path d="M24 6 26 24 22 24Z" fill="#22d3ee" stroke="#22d3ee" />
        <path d="M24 42 26 24 22 24Z" fill="#34d399" stroke="#34d399" />
        <path d="M6 24 24 26 24 22Z" fill="#22d3ee" stroke="#22d3ee" />
        <path d="M42 24 24 26 24 22Z" fill="#d97706" stroke="#d97706" />
      </g>
      <circle cx="24" cy="24" r="2.6" fill="#e8eef6" />
      <g
        className={labelClassName}
        fill="currentColor"
        fontSize="7.5"
        fontWeight="700"
        fontFamily="Manrope Variable, PingFang SC, Microsoft YaHei, sans-serif"
        textAnchor="middle"
      >
        <text x="24" y="2.5">卖什么</text>
        <text x="24" y="46.5">值得卖</text>
        <text x="2" y="26.5">怎么卖</text>
        <text x="46" y="26.5">卖到哪</text>
      </g>
    </svg>
  );
}
