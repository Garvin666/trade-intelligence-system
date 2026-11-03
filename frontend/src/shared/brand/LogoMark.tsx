import { useMemo, type CSSProperties } from "react";
import { cn } from "@/shared/lib/utils";
import logoUrl from "@/assets/logo-ship.png?inline";

interface LogoMarkProps {
  size?: number;
  className?: string;
  mono?: boolean;
}

interface StarConfig {
  left: number;
  top: number;
  delay: number;
  duration: number;
  scale: number;
}

function cssVars(vars: Record<string, string | number>): CSSProperties {
  return vars as CSSProperties;
}

const STAR_COUNT = 7;

export function LogoMark({ size = 36, className, mono = false }: LogoMarkProps) {
  const stars = useMemo<StarConfig[]>(
    () =>
      Array.from({ length: STAR_COUNT }, (_, index) => ({
        left: 8 + ((index * 37 + 13) % 84),
        top: 6 + ((index * 29 + 41) % 88),
        delay: (index * 0.37) % 2.1,
        duration: 2.2 + (index % 3) * 0.7,
        scale: 0.55 + (index % 4) * 0.18,
      })),
    [],
  );

  return (
    <span
      className={cn("logo-mark", mono && "logo-mark--mono", className)}
      style={cssVars({ "--logo-size": `${size}px`, width: size, height: size })}
    >
      <span className="logo-halo" aria-hidden="true" />
      <span className="logo-orbit" aria-hidden="true" />
      {stars.map((star, index) => (
        <span
          key={index}
          className="logo-star"
          aria-hidden="true"
          style={cssVars({
            "--star-left": `${star.left}%`,
            "--star-top": `${star.top}%`,
            "--star-delay": `${star.delay.toFixed(2)}s`,
            "--star-duration": `${star.duration.toFixed(2)}s`,
            "--star-scale": star.scale.toFixed(2),
          })}
        />
      ))}
      <img
        src={logoUrl}
        width={size}
        height={size}
        alt="远帆智品"
        aria-hidden={mono ? true : undefined}
        role={mono ? undefined : "img"}
        aria-label={mono ? undefined : "远帆智品"}
        className="logo-mark__img"
      />
      <span className="logo-sheen" aria-hidden="true" />
    </span>
  );
}
