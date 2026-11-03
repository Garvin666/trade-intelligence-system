import { useEffect, useRef, type CSSProperties } from "react";
import { cn } from "@/shared/lib/utils";
import { usePrefersReducedMotion } from "@/shared/hooks/usePrefersReducedMotion";

export type StarfieldVariant =
  | "agent"
  | "dashboard"
  | "workbench"
  | "trade"
  | "plans"
  | "system"
  | "about"
  | "demo";

const ACCENT_RGB: Record<StarfieldVariant, string> = {
  agent: "103 232 249",
  dashboard: "56 189 248",
  workbench: "196 181 253",
  trade: "251 191 36",
  plans: "52 211 153",
  system: "251 113 133",
  about: "253 224 71",
  demo: "125 211 252",
};

interface Star {
  x: number;
  y: number;
  depth: number;
  radius: number;
  alpha: number;
  phase: number;
  speed: number;
  frequency: number;
  color: [number, number, number];
  bright: boolean;
}

interface Meteor {
  x: number;
  y: number;
  vx: number;
  vy: number;
  age: number;
  life: number;
  length: number;
}

interface Dust {
  x: number;
  y: number;
  radius: number;
  alpha: number;
  speed: number;
  phase: number;
  color: [number, number, number];
}

interface StarfieldBackgroundProps {
  variant?: StarfieldVariant;
  className?: string;
}

function mulberry32(seed: number) {
  let state = seed >>> 0;
  return () => {
    state += 0x6d2b79f5;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function variantSeed(variant: StarfieldVariant): number {
  let hash = 2166136261;
  for (let i = 0; i < variant.length; i += 1) {
    hash ^= variant.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

export function StarfieldBackground({
  variant = "dashboard",
  className,
}: StarfieldBackgroundProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const reduced = usePrefersReducedMotion();

  useEffect(() => {
    const root = rootRef.current;
    const canvas = canvasRef.current;
    if (!root || !canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const rng = mulberry32(variantSeed(variant));
    const accent: [number, number, number] = ACCENT_RGB[variant]
      .split(" ")
      .map(Number) as [number, number, number];
    const dpr = Math.min(window.devicePixelRatio || 1, 1.75);
    let width = Math.max(1, root.clientWidth || window.innerWidth);
    let height = Math.max(1, root.clientHeight || window.innerHeight);
    let visible = document.visibilityState === "visible";
    let pointer = { x: 0.5, y: 0.5 };
    const pointerSmooth = { x: 0.5, y: 0.5 };
    const pointerVelocity = { x: 0, y: 0 };

    const updateSize = () => {
      width = Math.max(1, root.clientWidth || window.innerWidth);
      height = Math.max(1, root.clientHeight || window.innerHeight);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
    };
    updateSize();

    const count = Math.round(
      Math.min(300, Math.max(96, (width * height) / 15000)),
    );
    const stars: Star[] = Array.from({ length: count }, () => {
      const depth = Math.pow(rng(), 1.22);
      const roll = rng();
      const color: [number, number, number] =
        roll < 0.54
          ? [232, 240, 255]
          : roll < 0.8
            ? [255, 255, 255]
            : roll < 0.93
              ? accent
              : [174, 198, 255];
      return {
        x: rng(),
        y: rng(),
        depth,
        radius: (0.35 + rng() * 1.55) * (0.4 + depth * 0.95),
        alpha: 0.28 + rng() * 0.56,
        phase: rng() * Math.PI * 2,
        speed: (0.006 + rng() * 0.02) * (0.35 + depth),
        frequency: 0.5 + rng() * 1.35,
        color,
        bright: rng() < 0.065,
      };
    });

    const dustCount = Math.round(
      Math.min(28, Math.max(12, (width * height) / 90000)),
    );
    const dust: Dust[] = Array.from({ length: dustCount }, () => ({
      x: rng(),
      y: rng(),
      radius: 46 + rng() * 92,
      alpha: 0.018 + rng() * 0.032,
      speed: 0.004 + rng() * 0.012,
      phase: rng() * Math.PI * 2,
      color: rng() < 0.7 ? accent : [176, 196, 255],
    }));

    let meteor: Meteor | null = null;
    let meteorTimer = 2.8 + rng() * 4;
    const positions = new Float32Array(stars.length * 2);

    const spawnMeteor = () => {
      const fromLeft = rng() > 0.5;
      meteor = {
        x: fromLeft ? -60 : width + 60,
        y: rng() * height * 0.52,
        vx: (fromLeft ? 1 : -1) * (2.6 + rng() * 2.2) * 60,
        vy: (1.7 + rng() * 1.5) * 60,
        age: 0,
        life: 0.9 + rng() * 0.8,
        length: 96 + rng() * 110,
      };
    };

    const wrap = (value: number, size: number) =>
      ((value % size) + size) % size;

    const drawStar = (
      star: Star,
      x: number,
      y: number,
      time: number,
    ) => {
      const twinkle =
        reduced ? 1 : 0.68 + 0.32 * Math.sin(time * star.frequency + star.phase);
      const alpha = star.alpha * twinkle;
      if (alpha < 0.02) return;

      const [r, g, b] = star.color;

      ctx.beginPath();
      ctx.arc(x, y, star.radius, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha.toFixed(3)})`;
      ctx.fill();

      if (star.bright && !reduced) {
        const flare = star.radius * 5.2;
        ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${(alpha * 0.34).toFixed(3)})`;
        ctx.lineWidth = 0.7;
        ctx.beginPath();
        ctx.moveTo(x - flare, y);
        ctx.lineTo(x + flare, y);
        ctx.moveTo(x, y - flare);
        ctx.lineTo(x, y + flare);
        ctx.stroke();
      }
    };

    const drawDust = (time: number, offsetX: number, offsetY: number) => {
      for (const mote of dust) {
        const x = wrap(
          mote.x * width +
            offsetX * 0.55 +
            Math.sin(time * (0.08 + mote.speed * 1.6) + mote.phase) *
              (18 + mote.speed * 420),
          width,
        );
        const y = wrap(
          mote.y * height +
            offsetY * 0.35 +
            Math.cos(time * (0.06 + mote.speed * 1.4) + mote.phase) *
              (14 + mote.speed * 360),
          height,
        );
        const gradient = ctx.createRadialGradient(
          x,
          y,
          0,
          x,
          y,
          mote.radius,
        );
        gradient.addColorStop(
          0,
          `rgba(${mote.color[0]}, ${mote.color[1]}, ${mote.color[2]}, ${mote.alpha.toFixed(3)})`,
        );
        gradient.addColorStop(1, "rgba(0, 0, 0, 0)");
        ctx.fillStyle = gradient;
        ctx.fillRect(
          x - mote.radius,
          y - mote.radius,
          mote.radius * 2,
          mote.radius * 2,
        );
      }
    };

    const draw = (now: number) => {
      const dt = Math.min((now - lastDraw) / 1000, 0.05);
      lastDraw = now;
      if (!visible) {
        raf = window.requestAnimationFrame(draw);
        return;
      }

      const time = now / 1000;
      const smoothFactor = reduced ? 1 : Math.min(1, dt * 4.2);
      pointerSmooth.x += (pointer.x - pointerSmooth.x) * smoothFactor;
      pointerSmooth.y += (pointer.y - pointerSmooth.y) * smoothFactor;
      pointerVelocity.x *= 0.9;
      pointerVelocity.y *= 0.9;
      const offsetX = (pointerSmooth.x - 0.5) * 26;
      const offsetY = (pointerSmooth.y - 0.5) * 16;

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, width, height);

      for (let i = 0; i < stars.length; i += 1) {
        const star = stars[i];
        let x = wrap(
          star.x * width + offsetX * star.depth + time * star.speed * star.depth * 72,
          width,
        );
        let y = wrap(star.y * height + offsetY * star.depth * 0.7, height);

        if (!reduced) {
          const influence = 116 + star.depth * 132;
          const dx = x - pointer.x * width;
          const dy = y - pointer.y * height;
          const distanceSquared = dx * dx + dy * dy;
          if (distanceSquared < influence * influence) {
            const distance = Math.sqrt(distanceSquared) || 1;
            const closeness = 1 - distance / influence;
            const pointerSpeed = Math.min(
              1,
              Math.hypot(pointerVelocity.x, pointerVelocity.y) * 2.4,
            );
            const push = closeness * closeness * star.depth * (13 + pointerSpeed * 8);
            x = wrap(x + (dx / distance) * push, width);
            y = wrap(y + (dy / distance) * push * 0.55, height);
          }
        }

        positions[i * 2] = x;
        positions[i * 2 + 1] = y;
      }

      drawDust(time, offsetX, offsetY);

      if (!reduced) {
        for (let i = 0; i < stars.length; i += 1) {
          const a = stars[i];
          if (a.depth < 0.3) continue;
          for (let j = i + 1; j < stars.length; j += 1) {
            const b = stars[j];
            if (b.depth < 0.3) continue;
            const dx = positions[i * 2] - positions[j * 2];
            const dy = positions[i * 2 + 1] - positions[j * 2 + 1];
            const maxDistance = 108 + (a.depth + b.depth) * 42;
            const distanceSquared = dx * dx + dy * dy;
            if (distanceSquared > maxDistance * maxDistance) continue;
            const distance = Math.sqrt(distanceSquared) || 1;
            const alpha = (1 - distance / maxDistance) * 0.16;
            ctx.strokeStyle = `rgba(${accent[0]}, ${accent[1]}, ${accent[2]}, ${alpha.toFixed(3)})`;
            ctx.lineWidth = 0.6;
            ctx.beginPath();
            ctx.moveTo(positions[i * 2], positions[i * 2 + 1]);
            ctx.lineTo(positions[j * 2], positions[j * 2 + 1]);
            ctx.stroke();
          }
        }
      }

      for (let i = 0; i < stars.length; i += 1) {
        drawStar(stars[i], positions[i * 2], positions[i * 2 + 1], time);
      }

      if (!reduced) {
        meteorTimer -= dt;
        if (meteorTimer <= 0) {
          spawnMeteor();
          meteorTimer = 4.5 + rng() * 8;
        }
        if (meteor) {
          meteor.age += dt;
          if (meteor.age >= meteor.life) {
            meteor = null;
          } else {
            meteor.x += meteor.vx * dt;
            meteor.y += meteor.vy * dt;
            const progress = meteor.age / meteor.life;
            const alpha = (1 - progress) * 0.9;
            const tx = meteor.x - (meteor.vx / Math.max(60, Math.abs(meteor.vx))) * meteor.length;
            const ty = meteor.y - (meteor.vy / Math.max(60, Math.abs(meteor.vy))) * meteor.length;
            const gradient = ctx.createLinearGradient(
              meteor.x,
              meteor.y,
              tx,
              ty,
            );
            gradient.addColorStop(
              0,
              `rgba(${accent[0]}, ${accent[1]}, ${accent[2]}, ${alpha.toFixed(3)})`,
            );
            gradient.addColorStop(1, "rgba(0, 0, 0, 0)");
            ctx.strokeStyle = gradient;
            ctx.lineWidth = 1.2;
            ctx.beginPath();
            ctx.moveTo(meteor.x, meteor.y);
            ctx.lineTo(tx, ty);
            ctx.stroke();
            ctx.beginPath();
            ctx.arc(meteor.x, meteor.y, 1.25, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(255, 255, 255, ${(alpha * 0.9).toFixed(3)})`;
            ctx.fill();
          }
        }
      }

      if (!reduced) {
        raf = window.requestAnimationFrame(draw);
      }
    };

    let raf = 0;
    let lastDraw = performance.now();

    if (!reduced) {
      raf = window.requestAnimationFrame(draw);
    } else {
      draw(lastDraw);
    }

    const onPointerMove = (event: PointerEvent) => {
      const nextX = event.clientX / Math.max(window.innerWidth, 1);
      const nextY = event.clientY / Math.max(window.innerHeight, 1);
      pointerVelocity.x = nextX - pointer.x;
      pointerVelocity.y = nextY - pointer.y;
      pointer = {
        x: nextX,
        y: nextY,
      };
      root.style.setProperty("--star-pointer-x", `${event.clientX}px`);
      root.style.setProperty("--star-pointer-y", `${event.clientY}px`);
    };
    const onVisibility = () => {
      visible = document.visibilityState === "visible";
    };
    const onResize = () => {
      updateSize();
      if (reduced) draw(performance.now());
    };

    window.addEventListener("pointermove", onPointerMove, { passive: true });
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("resize", onResize);

    return () => {
      window.cancelAnimationFrame(raf);
      window.removeEventListener("pointermove", onPointerMove);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("resize", onResize);
    };
  }, [reduced, variant]);

  return (
    <div
      ref={rootRef}
      data-starfield={variant}
      aria-hidden="true"
      className={cn("starfield-bg", className)}
      style={
        {
          "--starfield-accent-rgb": ACCENT_RGB[variant],
        } as CSSProperties
      }
    >
      <canvas ref={canvasRef} />
    </div>
  );
}
