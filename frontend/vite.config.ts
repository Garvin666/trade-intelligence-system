import path from "node:path";
import fs from "node:fs";
import zlib from "node:zlib";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv, type Plugin } from "vite";
import { viteSingleFile } from "vite-plugin-singlefile";

const frontendRoot = import.meta.dirname;
const projectRoot = path.resolve(frontendRoot, "..");
const srcRoot = path.resolve(frontendRoot, "src");

export default defineConfig(({ mode }) => {
  const offline = mode === "offline";
  // 从项目根 .env 读取 VITE_*（与后端共享同一份配置源，见 .env.example）
  const env = loadEnv(mode, projectRoot, "VITE_");
  const proxyTarget = env.VITE_PROXY_TARGET || "http://127.0.0.1:8000";
  return {
    // 让 import.meta.env.VITE_*（如 VITE_API_BASE）从项目根 .env 注入
    envDir: projectRoot,
    plugins: [
      react(),
      tailwindcss(),
      ...(offline
        ? [
            viteSingleFile(),
            {
              name: "yuanfan-inject-dashboard-data",
              enforce: "post",
              transformIndexHtml: {
                order: "post",
                handler: (html: string) => {
                  const dataPath = path.resolve(projectRoot, "output/dashboard-data.json");
                  if (!fs.existsSync(dataPath)) {
                    return html;
                  }
                  // gzip + base64：剥离缩进后压缩再内联，显著减小单文件体积；
                  // 浏览器端在 main.tsx 启动时解压回 window.__TRADE_INTEL_OFFLINE__。
                  let payload: string;
                  try {
                    const raw = JSON.stringify(
                      JSON.parse(fs.readFileSync(dataPath, "utf-8")),
                    );
                    payload = zlib.gzipSync(Buffer.from(raw, "utf-8")).toString("base64");
                  } catch (err) {
                    throw new Error(
                      `[yuanfan-inject-dashboard-data] 无法解析 ${dataPath}: ${String(err)}`,
                      { cause: err },
                    );
                  }
                  const logoPath = path.resolve(projectRoot, "assets/logo-ship.png");
                  const logoData = fs.existsSync(logoPath)
                    ? `data:image/png;base64,${fs.readFileSync(logoPath).toString("base64")}`
                    : "";
                  let nextHtml = html.replace(
                    "</body>",
                    // 转义 </script> 序列，避免数据内容提前闭合标签
                    `<script>window.__TRADE_INTEL_OFFLINE_GZIP__="${payload}";</script></body>`,
                  );
                  if (logoData) {
                    nextHtml = nextHtml.replace(
                      /href="(?:\.\/)?favicon\.png"/,
                      `href="${logoData}"`,
                    );
                  }
                  return nextHtml;
                },
              },
            } satisfies Plugin,
          ]
        : []),
    ],
    resolve: {
      alias: {
        "@": srcRoot,
      },
    },
    base: offline ? "./" : "/app/",
    build: {
      outDir: offline ? "dist-offline" : "dist",
      chunkSizeWarningLimit: 4096,
      assetsInlineLimit: 8192,
      rollupOptions: offline
        ? {}
        : {
            output: {
              manualChunks: (id: string) => {
                if (id.includes("echarts")) return "echarts";
                if (id.includes("node_modules/react")) return "react";
                return undefined;
              },
            },
          },
    },
    server: {
      port: 5173,
      proxy: {
        "/api": proxyTarget,
        "/output": proxyTarget,
      },
    },
    define: {
      "import.meta.env.VITE_OFFLINE": JSON.stringify(offline ? "1" : "0"),
    },
  };
});
