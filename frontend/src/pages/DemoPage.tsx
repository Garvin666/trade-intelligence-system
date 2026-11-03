import { DynamicDemoSection } from "@/features/demo/DynamicDemoSection";
import { useTransitionNavigate } from "@/widgets/RouteTransition";
import { StarfieldBackground } from "@/shared/motion/StarfieldBackground";

export default function DemoPage() {
  const transitionNavigate = useTransitionNavigate();

  return (
    <div className="relative min-h-screen">
      <StarfieldBackground variant="demo" />
      <main className="relative z-10">
        <DynamicDemoSection
          hideDeckToggle
          onBack={() => transitionNavigate("/")}
        />
      </main>
    </div>
  );
}
