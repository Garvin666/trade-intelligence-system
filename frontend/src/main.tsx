import React from "react";
import ReactDOM from "react-dom/client";
import "@fontsource-variable/manrope";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/600.css";
import "@/shared/styles/app.css";
import { App } from "@/app/App";
import { IS_OFFLINE, initOfflineData } from "@/shared/api/offline";

async function bootstrap() {
  if (IS_OFFLINE) {
    await initOfflineData();
  }
  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
}

void bootstrap();
