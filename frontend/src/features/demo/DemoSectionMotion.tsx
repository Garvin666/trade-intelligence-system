import { useEffect, useRef, type ReactNode } from "react";
import { gsap } from "gsap";
import { usePrefersReducedMotion } from "@/shared/hooks/usePrefersReducedMotion";

export function DemoSectionMotion({ children }: { children: ReactNode }) {
  const rootRef = useRef<HTMLDivElement>(null);
  const reduced = usePrefersReducedMotion();

  useEffect(() => {
    const root = rootRef.current;
    if (reduced || !root) return;
    const ctx = gsap.context(() => {
      const coarse = window.matchMedia("(pointer: coarse)").matches;
      if (coarse) return;
      gsap.utils.toArray<HTMLElement>(".tilt-card", root).forEach((card) => {
        const rotateX = gsap.quickTo(card, "rotationX", {
          duration: 0.45,
          ease: "power2.out",
        });
        const rotateY = gsap.quickTo(card, "rotationY", {
          duration: 0.45,
          ease: "power2.out",
        });
        const onMove = (event: PointerEvent) => {
          const rect = card.getBoundingClientRect();
          if (!rect.width || !rect.height) return;
          rotateY(((event.clientX - rect.left) / rect.width - 0.5) * 10);
          rotateX(-((event.clientY - rect.top) / rect.height - 0.5) * 10);
        };
        const onLeave = () => {
          rotateX(0);
          rotateY(0);
        };
        card.addEventListener("pointermove", onMove);
        card.addEventListener("pointerleave", onLeave);
      });
    }, root);
    return () => ctx.revert();
  }, [reduced]);

  return (
    <div ref={rootRef} className="demo-motion-scene">
      {children}
    </div>
  );
}
