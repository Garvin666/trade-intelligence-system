import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { usePrefersReducedMotion } from "@/shared/hooks/usePrefersReducedMotion";
import { cn } from "@/shared/lib/utils";
import { Page3DSceneStatic, type SceneVariant } from "./Page3DSceneStatic";

interface Page3DSceneCoreProps {
  height?: number;
  className?: string;
  variant?: SceneVariant;
}

function supportsWebGL(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return !!(
      canvas.getContext("webgl2") ||
      canvas.getContext("webgl")
    );
  } catch {
    return false;
  }
}

/** 各系统专属核心几何：看板=六棱柱（六维）、四脑=中心球+四脑环绕、贸易=决策环+卫星、默认=八面体 */
function buildCore(
  group: THREE.Group,
  variant: SceneVariant,
  disposables: Array<{ dispose: () => void }>,
): { cores: THREE.Mesh[]; baseColors: number[] } {
  const cores: THREE.Mesh[] = [];
  const baseColors: number[] = [];

  const addMesh = (
    geometry: THREE.BufferGeometry,
    color: number,
    opacity = 0.85,
  ): THREE.Mesh => {
    const material = new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity,
      depthWrite: false,
    });
    const mesh = new THREE.Mesh(geometry, material);
    group.add(mesh);
    disposables.push(geometry, material);
    cores.push(mesh);
    baseColors.push(color);
    return mesh;
  };

  if (variant === "dashboard") {
    // 六棱柱：六维评分
    const core = addMesh(new THREE.CylinderGeometry(0.62, 0.62, 1.05, 6), 0x67e8f9);
    core.rotation.x = 0.25;
    const wire = addMesh(
      new THREE.CylinderGeometry(0.82, 0.82, 1.35, 6, 1, true),
      0x22d3ee,
      0.22,
    );
    wire.rotation.x = 0.25;
  } else if (variant === "workbench") {
    // 中心核心 + 四脑环绕
    addMesh(new THREE.OctahedronGeometry(0.4), 0x67e8f9);
    for (let i = 0; i < 4; i += 1) {
      const angle = (i / 4) * Math.PI * 2;
      const satellite = addMesh(
        new THREE.OctahedronGeometry(0.22),
        [0x22d3ee, 0xd97706, 0x34d399, 0x22d3ee][i],
      );
      satellite.position.set(Math.cos(angle) * 1.05, Math.sin(angle * 2) * 0.15, Math.sin(angle) * 1.05);
      satellite.userData.orbit = angle;
    }
  } else if (variant === "trade") {
    // 决策环 + 卫星
    addMesh(new THREE.TorusGeometry(0.85, 0.045, 10, 48), 0x22d3ee, 0.55);
    addMesh(new THREE.SphereGeometry(0.34, 20, 20), 0x67e8f9);
    const satellite = addMesh(new THREE.SphereGeometry(0.12, 12, 12), 0xf59e0b);
    satellite.position.set(0.85, 0, 0);
    satellite.userData.orbit = 0;
  } else if (variant === "agent") {
    // 智能体核心：处理器方块 + 线框 + 三枚工具/确认轨道
    const core = addMesh(new THREE.BoxGeometry(0.62, 0.62, 0.62), 0x67e8f9);
    core.rotation.x = 0.32;
    core.rotation.y = 0.46;
    const wire = addMesh(
      new THREE.BoxGeometry(0.84, 0.84, 0.84),
      0x22d3ee,
      0.22,
    );
    wire.rotation.x = 0.32;
    wire.rotation.y = 0.46;
    const colors = [0x22d3ee, 0xf59e0b, 0x34d399];
    for (let i = 0; i < 3; i += 1) {
      const angle = (i / 3) * Math.PI * 2;
      const satellite = addMesh(
        new THREE.OctahedronGeometry(0.16),
        colors[i],
      );
      satellite.position.set(
        Math.cos(angle) * 1.05,
        Math.sin(angle * 2) * 0.15,
        Math.sin(angle) * 1.05,
      );
      satellite.userData.orbit = angle;
    }
  } else {
    // 默认：八面体 + 线框
    addMesh(new THREE.OctahedronGeometry(0.62), 0x67e8f9);
    addMesh(
      new THREE.OctahedronGeometry(0.82),
      0x22d3ee,
      0.22,
    );
  }

  return { cores, baseColors };
}

export function Page3DSceneCore({
  height = 150,
  className,
  variant = "default",
}: Page3DSceneCoreProps) {
  const reduced = usePrefersReducedMotion();
  const [webgl] = useState(supportsWebGL);
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stateRef = useRef({
    pointerX: 0,
    pointerY: 0,
  });

  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!webgl || reduced || !container || !canvas) return;

    const renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: true,
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(
      55,
      container.clientWidth / Math.max(container.clientHeight, 1),
      0.1,
      100,
    );
    camera.position.set(0, 0.4, 7);
    camera.lookAt(0, 0, 0);

    const group = new THREE.Group();
    scene.add(group);
    const disposables: Array<{ dispose: () => void }> = [];

    const ringColors = ["#22D3EE", "#F59E0B", "#34D399"];
    ringColors.forEach((color, index) => {
      const geometry = new THREE.TorusGeometry(1.5 + index * 0.28, 0.024, 12, 64);
      const material = new THREE.MeshBasicMaterial({
        color,
        transparent: true,
        opacity: 0.34 - index * 0.05,
        depthWrite: false,
      });
      const ring = new THREE.Mesh(geometry, material);
      ring.rotation.x = Math.PI / 2 + index * 0.45;
      ring.rotation.z = index * 0.7;
      group.add(ring);
      disposables.push(geometry, material);
    });

    const { cores } = buildCore(group, variant, disposables);
    const core = cores[0];

    const particleCount = 160;
    const positions = new Float32Array(particleCount * 3);
    for (let i = 0; i < particleCount; i += 1) {
      positions[i * 3] = (Math.random() - 0.5) * 12;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 4;
      positions[i * 3 + 2] = (Math.random() - 0.5) * 8;
    }
    const particleGeometry = new THREE.BufferGeometry();
    particleGeometry.setAttribute(
      "position",
      new THREE.BufferAttribute(positions, 3),
    );
    const particleMaterial = new THREE.PointsMaterial({
      color: 0x67e8f9,
      size: 0.055,
      transparent: true,
      opacity: 0.5,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const particles = new THREE.Points(particleGeometry, particleMaterial);
    group.add(particles);
    disposables.push(particleGeometry, particleMaterial);

    const timer = new THREE.Timer();
    let inView = true;

    const resize = () => {
      const width = container.clientWidth;
      const height = container.clientHeight;
      if (!width || !height) return;
      renderer.setSize(width, height);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    resize();

    const animate = () => {
      const dt = Math.min(timer.getDelta(), 0.05);
      const elapsed = timer.getElapsed();

      // 自动巡航 + 指针视差（用户当前版本要求交互式 3D）
      group.rotation.y = elapsed * 0.22;
      group.rotation.x = Math.sin(elapsed * 0.18) * 0.08;

      if (core) {
        core.rotation.x += dt * 0.5;
        core.rotation.y += dt * 0.7;
      }
      for (const mesh of cores.slice(1)) {
        mesh.rotation.x -= dt * 0.3;
        mesh.rotation.y += dt * 0.4;
        if (mesh.userData.orbit !== undefined) {
          mesh.userData.orbit += dt * 0.9;
          mesh.position.x = Math.cos(mesh.userData.orbit) * 1.05;
          mesh.position.z = Math.sin(mesh.userData.orbit) * 1.05;
        }
      }
      particles.rotation.y += dt * 0.03;

      const state = stateRef.current;
      camera.position.x += (state.pointerX * 0.9 - camera.position.x) * 0.035;
      camera.position.y += (
        state.pointerY * 0.45 +
        0.4 -
        camera.position.y
      ) * 0.035;
      camera.lookAt(0, 0, 0);
      renderer.render(scene, camera);
    };

    const onPointerMove = (event: PointerEvent) => {
      const rect = container.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      stateRef.current.pointerX = (event.clientX - rect.left) / rect.width - 0.5;
      stateRef.current.pointerY = (event.clientY - rect.top) / rect.height - 0.5;
    };

    container.addEventListener("pointermove", onPointerMove);
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(container);
    const intersectionObserver = new IntersectionObserver(
      (entries) => {
        const visible = entries[0]?.isIntersecting ?? false;
        if (visible && !inView) {
          inView = true;
          renderer.setAnimationLoop(animate);
        } else if (!visible && inView) {
          inView = false;
          renderer.setAnimationLoop(null);
        }
      },
      { threshold: 0.05 },
    );
    intersectionObserver.observe(container);
    renderer.setAnimationLoop(animate);

    return () => {
      renderer.setAnimationLoop(null);
      intersectionObserver.disconnect();
      resizeObserver.disconnect();
      container.removeEventListener("pointermove", onPointerMove);
      disposables.forEach((item) => item.dispose());
      renderer.dispose();
    };
  }, [reduced, webgl, variant]);

  if (!webgl || reduced) {
    // WebGL 不可用或用户开启"减少动态效果"时，用 CSS 3D 场景面板替代
    return <Page3DSceneStatic height={height} className={className} variant={variant} />;
  }

  return (
    <div
      ref={containerRef}
      className={cn(
        "relative overflow-hidden rounded-xl border border-white/10 bg-raised/70",
        className,
      )}
      style={{ height }}
      aria-hidden="true"
    >
      <canvas ref={canvasRef} className="h-full w-full" />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_45%,rgba(34,211,238,.08),transparent_62%)]" />
    </div>
  );
}
