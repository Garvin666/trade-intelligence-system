import { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useGlobeMarketPicks } from "@/shared/api/hooks";
import EarthScene, { type EarthSceneMode } from "./EarthScene";
import { useEarthTransitionStore } from "./earthTransitionStore";
import { MARKET_LOCATIONS, type MarketLocation } from "./markets";

function normalizePath(path: string): string {
  return path.split("?")[0].replace(/\/+$/, "") || "/";
}

export function GlobeStage() {
  const navigate = useNavigate();
  const location = useLocation();
  const path = normalizePath(location.pathname);
  const status = useEarthTransitionStore((state) => state.status);
  const begin = useEarthTransitionStore((state) => state.begin);
  const reset = useEarthTransitionStore((state) => state.reset);
  const [selectedMarket, setSelectedMarket] = useState<MarketLocation | null>(
    null,
  );

  const isHome = path === "/";
  const isGlobe = path === "/globe";
  const marketIds = MARKET_LOCATIONS.map((market) => market.id);
  const { data: marketPicks } = useGlobeMarketPicks(marketIds, {
    enabled: isHome || isGlobe,
  });

  const handleGlobeClick = useCallback(() => {
    if (isHome && status === "idle") {
      setSelectedMarket(null);
      begin();
    } else if (isGlobe && selectedMarket) {
      setSelectedMarket(null);
    }
  }, [begin, isGlobe, isHome, selectedMarket, status]);

  const handleMarketSelect = useCallback(
    (market: MarketLocation) => {
      if (isHome && status === "idle") {
        setSelectedMarket(market);
        begin();
      } else if (isGlobe) {
        setSelectedMarket(market);
      }
    },
    [begin, isGlobe, isHome, status],
  );

  const handleGlobeEnterComplete = useCallback(() => {
    if (status === "leaving") {
      navigate("/globe");
    }
  }, [navigate, status]);

  useEffect(() => {
    if (isGlobe && status === "leaving") {
      reset();
    }
  }, [isGlobe, reset, status]);

  if (!isHome && !isGlobe) {
    return null;
  }

  const mode: EarthSceneMode =
    isHome && status === "idle" ? "hero" : "full";

  return (
    <div className="globe-stage">
      <EarthScene
        mode={mode}
        className={isHome ? "home-globe-scene" : "full-globe-scene"}
        onGlobeClick={handleGlobeClick}
        onGlobeEnterComplete={handleGlobeEnterComplete}
        onMarketSelect={handleMarketSelect}
        focusMarket={selectedMarket}
        marketPicks={marketPicks}
      />
    </div>
  );
}
