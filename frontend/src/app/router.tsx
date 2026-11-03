import { lazy, Suspense } from "react";
import { BrowserRouter, HashRouter, Route, Routes } from "react-router-dom";
import { IS_OFFLINE } from "@/shared/api/offline";
import { AppShell } from "@/widgets/AppShell";
import { LoadingScreen } from "@/widgets/LoadingScreen";
import { RouteTransitionProvider } from "@/widgets/RouteTransition";
import { GlobeStage } from "@/globe/GlobeStage";

const HomePage = lazy(() => import("@/pages/HomePage"));
const AgentPage = lazy(() => import("@/pages/AgentPage"));
const DemoPage = lazy(() => import("@/pages/DemoPage"));
const DashboardPage = lazy(() => import("@/pages/DashboardPage"));
const WorkbenchPage = lazy(() => import("@/pages/WorkbenchPage"));
const TradePage = lazy(() => import("@/pages/TradePage"));
const PlansPage = lazy(() => import("@/pages/PlansPage"));
const SystemPage = lazy(() => import("@/pages/SystemPage"));
const AboutPage = lazy(() => import("@/pages/AboutPage"));
const EarthPage = lazy(() => import("@/pages/EarthPage"));

function AppRoutes() {
  return (
    <Suspense fallback={<LoadingScreen />}>
      <Routes>
        <Route path="demo" element={<DemoPage />} />
        <Route path="globe" element={<EarthPage />} />
        <Route element={<AppShell />}>
          <Route index element={<HomePage />} />
          <Route path="agent" element={<AgentPage />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="workbench" element={<WorkbenchPage />} />
          <Route path="trade" element={<TradePage />} />
          <Route path="plans" element={<PlansPage />} />
          <Route path="system" element={<SystemPage />} />
          <Route path="about" element={<AboutPage />} />
          <Route path="*" element={<HomePage />} />
        </Route>
      </Routes>
    </Suspense>
  );
}

function RouterContent() {
  return (
    <RouteTransitionProvider>
      <GlobeStage />
      <AppRoutes />
    </RouteTransitionProvider>
  );
}

export function AppRouter() {
  if (IS_OFFLINE) {
    return (
      <HashRouter>
        <RouterContent />
      </HashRouter>
    );
  }
  return (
    <BrowserRouter basename="/app">
      <RouterContent />
    </BrowserRouter>
  );
}
