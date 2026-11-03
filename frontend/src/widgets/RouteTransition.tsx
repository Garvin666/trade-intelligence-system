import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  type ReactNode,
} from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { gsap } from "gsap";
import { usePrefersReducedMotion } from "@/shared/hooks/usePrefersReducedMotion";

const NAV_ORDER = [
  "/",
  "/demo",
  "/dashboard",
  "/workbench",
  "/trade",
  "/system",
  "/about",
];

interface RouteTransitionContextValue {
  transitionNavigate: (to: string) => void;
}

const RouteTransitionContext = createContext<RouteTransitionContextValue>({
  transitionNavigate: () => undefined,
});

export function useTransitionNavigate(): (to: string) => void {
  return useContext(RouteTransitionContext).transitionNavigate;
}

function normalizePath(path: string): string {
  const clean = path.split("?")[0].replace(/\/+$/, "") || "/";
  return clean;
}

function resetScroll(): void {
  const root = document.documentElement;
  root.style.scrollBehavior = "auto";
  window.scrollTo(0, 0);
  root.style.scrollBehavior = "";
}

export function RouteTransitionProvider({ children }: { children: ReactNode }) {
  const location = useLocation();
  const navigate = useNavigate();
  const reduced = usePrefersReducedMotion();
  const overlayRef = useRef<HTMLDivElement>(null);
  const timelineRef = useRef<gsap.core.Timeline | null>(null);

  const transitionNavigate = useCallback(
    (to: string) => {
      if (reduced) {
        navigate(to);
        return;
      }
      const overlay = overlayRef.current;
      if (!overlay) {
        navigate(to);
        return;
      }
      const currentPath = normalizePath(location.pathname);
      const targetPath = normalizePath(to);
      const currentIndex = NAV_ORDER.indexOf(currentPath);
      const targetIndex = NAV_ORDER.indexOf(targetPath);
      const forward =
        targetIndex < 0 || targetIndex > currentIndex || currentIndex < 0;
      const dir = forward ? 1 : -1;

      timelineRef.current?.kill();
      const tl = gsap.timeline({ defaults: { ease: "power2.out" } });
      timelineRef.current = tl;

      tl.set(overlay, {
        autoAlpha: 0,
        y: 0,
        visibility: "visible",
        pointerEvents: "auto",
      })
        .fromTo(
          overlay,
          { autoAlpha: 0, y: 10 * dir, xPercent: 0 },
          { autoAlpha: 1, y: 0, duration: 0.12 },
        )
        .call(() => {
          resetScroll();
          navigate(to);
        })
        .to(overlay, { autoAlpha: 0, y: -8 * dir, duration: 0.16 })
        .set(overlay, { pointerEvents: "none" });
    },
    [location.pathname, navigate, reduced],
  );

  const value = useMemo(() => ({ transitionNavigate }), [transitionNavigate]);

  useEffect(() => {
    return () => {
      timelineRef.current?.kill();
    };
  }, []);

  return (
    <RouteTransitionContext.Provider value={value}>
      {children}
      <div
        ref={overlayRef}
        className="route-overlay"
        aria-hidden="true"
      />
    </RouteTransitionContext.Provider>
  );
}
