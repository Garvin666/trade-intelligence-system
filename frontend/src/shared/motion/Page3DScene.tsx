import { lazy, Suspense } from "react";
import { Page3DSceneStatic, type SceneVariant } from "./Page3DSceneStatic";

interface Page3DSceneProps {
  height?: number;
  className?: string;
  variant?: SceneVariant;
}

const Page3DSceneCore = lazy(() =>
  import("./Page3DSceneCore").then((module) => ({
    default: module.Page3DSceneCore,
  })),
);

export function Page3DScene({
  height = 150,
  className,
  variant = "default",
}: Page3DSceneProps) {
  return (
    <Suspense
      fallback={
        <Page3DSceneStatic height={height} className={className} variant={variant} />
      }
    >
      <Page3DSceneCore height={height} className={className} variant={variant} />
    </Suspense>
  );
}
