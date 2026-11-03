import { useEffect } from "react";
import { IS_OFFLINE } from "@/shared/api/offline";
import { useTradeIntelStore } from "@/shared/store/trade-intel";
import { AppProviders } from "./providers";
import { AppRouter } from "./router";

export function App() {
  const setOffline = useTradeIntelStore((state) => state.setOffline);

  useEffect(() => {
    setOffline(IS_OFFLINE);
  }, [setOffline]);

  return (
    <AppProviders>
      <AppRouter />
    </AppProviders>
  );
}
