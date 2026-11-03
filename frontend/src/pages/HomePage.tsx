import { EarthHero } from "@/widgets/EarthHero";
import { useEarthTransitionStore } from "@/globe/earthTransitionStore";

export default function HomePage() {
  const entering = useEarthTransitionStore((state) => state.status === "leaving");

  return (
    <div className="home-earth-stage">
      <div
        className={`home-earth-content ${entering ? "is-leaving" : ""}`}
        aria-hidden={entering}
      >
        <EarthHero />
      </div>
    </div>
  );
}
