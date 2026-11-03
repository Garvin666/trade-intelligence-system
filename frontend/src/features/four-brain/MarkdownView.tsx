import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

const components: Components = {
  a: ({ href, children, ...props }) => (
    <a href={href} target="_blank" rel="noreferrer" {...props}>
      {children}
    </a>
  ),
};

export function MarkdownView({ content }: { content: string }) {
  return (
    <div className="markdown-body">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
