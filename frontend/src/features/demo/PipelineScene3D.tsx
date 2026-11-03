import {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import { Pause, Play, RotateCcw } from "lucide-react";
import * as THREE from "three";
import { Badge } from "@/shared/ui/badge";
import { Button } from "@/shared/ui/button";
import { cn } from "@/shared/lib/utils";
import { usePrefersReducedMotion } from "@/shared/hooks/usePrefersReducedMotion";
import { DEMO_STAGES } from "./DEMO_STAGES";
import { SystemFlowDiagram } from "./SystemFlowDiagram";

const STAGE_COLORS = [
  "#22D3EE",
  "#38BDF8",
  "#34D399",
  "#F59E0B",
  "#E879F9",
  "#2DD4BF",
];

const SPEEDS = [1, 2, 4] as const;
const NOOP = () => undefined;

interface PipelineScene3DProps {
  activeStageId?: string;
  onStageChange?: (id: string) => void;
  playing?: boolean;
  onTogglePlaying?: () => void;
  speed?: number;
  onSpeedChange?: (speed: number) => void;
}

interface StageNode {
  id: string;
  mesh: THREE.Mesh;
  ring: THREE.Mesh;
  material: THREE.MeshStandardMaterial;
  sprite: THREE.Sprite;
}

interface EdgeRig {
  curve: THREE.CatmullRomCurve3;
  points: THREE.Points;
  geometry: THREE.BufferGeometry;
  count: number;
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

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function makeLabelSprite(text: string, color: string): THREE.Sprite {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 96;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.font = "700 38px 'Manrope Variable', 'Microsoft YaHei', sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.shadowColor = "rgba(2,8,18,0.85)";
    ctx.shadowBlur = 18;
    ctx.fillStyle = "#E8EEF6";
    ctx.fillText(text, canvas.width / 2, canvas.height / 2);
    ctx.shadowBlur = 0;
    ctx.fillStyle = color;
    ctx.globalAlpha = 0.9;
    ctx.fillRect(canvas.width / 2 - 34, canvas.height - 14, 68, 3);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthWrite: false,
  });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(3.1, 0.58, 1);
  return sprite;
}

export function PipelineScene3D({
  activeStageId = DEMO_STAGES[0].id,
  onStageChange = NOOP,
  playing = true,
  onTogglePlaying = NOOP,
  speed = 1,
  onSpeedChange = NOOP,
}: PipelineScene3DProps) {
  const reduced = usePrefersReducedMotion();
  const [webgl] = useState(supportsWebGL);

  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const nodeMapRef = useRef(new Map<string, StageNode>());
  const edgeRigsRef = useRef<EdgeRig[]>([]);
  const stateRef = useRef({
    playing,
    speed,
    selectedId: activeStageId,
    hoveredId: null as string | null,
    radius: 11,
    targetRadius: 11,
    theta: 0.35,
    targetTheta: 0.35,
    phi: 1.05,
    targetPhi: 1.05,
    pointerDown: false,
    pointerMoved: false,
    lastX: 0,
    lastY: 0,
    pointerNdc: new THREE.Vector2(),
  });

  useEffect(() => {
    stateRef.current.playing = playing;
  }, [playing]);

  useEffect(() => {
    stateRef.current.speed = speed;
  }, [speed]);

  useEffect(() => {
    stateRef.current.selectedId = activeStageId;
  }, [activeStageId]);

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
    camera.position.set(0, 2.4, 12);
    camera.lookAt(0, 0, 0);

    scene.add(new THREE.AmbientLight(0xffffff, 1.6));
    const keyLight = new THREE.DirectionalLight(0xffffff, 2.4);
    keyLight.position.set(4, 8, 6);
    scene.add(keyLight);
    const rimLight = new THREE.DirectionalLight(0x22d3ee, 1.2);
    rimLight.position.set(-5, -2, -4);
    scene.add(rimLight);

    const group = new THREE.Group();
    scene.add(group);

    const disposables: Array<{
      dispose: () => void;
    }> = [];
    const nodeMap = nodeMapRef.current;
    const edgeRigs = edgeRigsRef.current;

    const stageCount = DEMO_STAGES.length;
    const nodePositions = DEMO_STAGES.map((stage, index) => {
      const t = stageCount === 1 ? 0.5 : index / (stageCount - 1);
      return {
        id: stage.id,
        x: -6.8 + t * 13.6,
        y: Math.sin(t * Math.PI) * 1.7 - 0.35,
        z: Math.sin(t * Math.PI * 2.2) * 1.9,
        color: STAGE_COLORS[index % STAGE_COLORS.length],
      };
    });

    nodePositions.forEach((node, index) => {
      const geometry = new THREE.SphereGeometry(0.72, 32, 24);
      const material = new THREE.MeshStandardMaterial({
        color: node.color,
        roughness: 0.32,
        metalness: 0.18,
        emissive: node.color,
        emissiveIntensity: 0.18,
      });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.set(node.x, node.y, node.z);
      mesh.userData.id = node.id;

      const ringGeometry = new THREE.TorusGeometry(1.08, 0.035, 12, 48);
      const ringMaterial = new THREE.MeshBasicMaterial({
        color: node.color,
        transparent: true,
        opacity: 0,
        depthWrite: false,
      });
      const ring = new THREE.Mesh(ringGeometry, ringMaterial);
      ring.position.copy(mesh.position);
      ring.rotation.x = Math.PI / 2;

      const sprite = makeLabelSprite(
        DEMO_STAGES[index].label,
        node.color,
      );
      sprite.position.set(node.x, node.y + 1.45, node.z);

      group.add(mesh, ring, sprite);
      const spriteMaterial = sprite.material as THREE.SpriteMaterial;
      if (spriteMaterial.map) {
        disposables.push(spriteMaterial.map);
      }
      disposables.push(spriteMaterial);
      nodeMap.set(node.id, {
        id: node.id,
        mesh,
        ring,
        material,
        sprite,
      });
      disposables.push(geometry, material, ringGeometry, ringMaterial);
    });

    nodePositions.forEach((node, index) => {
      const next = nodePositions[index + 1];
      if (!next) return;
      const curve = new THREE.CatmullRomCurve3(
        [
          new THREE.Vector3(node.x, node.y, node.z),
          new THREE.Vector3(
            (node.x + next.x) / 2,
            (node.y + next.y) / 2 - 0.8,
            (node.z + next.z) / 2 + 0.5,
          ),
          new THREE.Vector3(next.x, next.y, next.z),
        ],
        false,
        "catmullrom",
        0.5,
      );
      const tubeGeometry = new THREE.TubeGeometry(curve, 48, 0.045, 8, false);
      const tubeMaterial = new THREE.MeshBasicMaterial({
        color: 0x67e8f9,
        transparent: true,
        opacity: 0.18,
        depthWrite: false,
      });
      const tube = new THREE.Mesh(tubeGeometry, tubeMaterial);
      group.add(tube);

      const count = 22;
      const positions = new Float32Array(count * 3);
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
      const material = new THREE.PointsMaterial({
        color: next.color,
        size: 0.16,
        transparent: true,
        opacity: 0.95,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      });
      const points = new THREE.Points(geometry, material);
      group.add(points);
      edgeRigs.push({
        curve,
        points,
        geometry,
        count,
      });
      disposables.push(tubeGeometry, tubeMaterial, geometry, material);
    });

    const raycaster = new THREE.Raycaster();
    const clock = new THREE.Clock();
    const lerpFactor = 0.07;
    const activePointers = new Map<number, { x: number; y: number }>();
    let lastPinchDistance = 0;

    const updateCamera = () => {
      const state = stateRef.current;
      state.theta += (state.targetTheta - state.theta) * lerpFactor;
      state.phi += (state.targetPhi - state.phi) * lerpFactor;
      state.radius += (state.targetRadius - state.radius) * lerpFactor;
      camera.position.set(
        state.radius * Math.sin(state.phi) * Math.sin(state.theta),
        state.radius * Math.cos(state.phi) + 1.4,
        state.radius * Math.sin(state.phi) * Math.cos(state.theta),
      );
      camera.lookAt(0, 0, 0);
    };

    const updateParticles = (elapsed: number) => {
      edgeRigs.forEach((edge, edgeIndex) => {
        const attribute = edge.geometry.attributes
          .position as THREE.BufferAttribute;
        const values = attribute.array as Float32Array;
        for (let i = 0; i < edge.count; i += 1) {
          const t =
            (elapsed * 0.14 + i / edge.count + edgeIndex * 0.13) % 1;
          const point = edge.curve.getPoint(t);
          values[i * 3] = point.x;
          values[i * 3 + 1] = point.y;
          values[i * 3 + 2] = point.z;
        }
        attribute.needsUpdate = true;
      });
    };

    const updateNodes = (elapsed: number) => {
      const state = stateRef.current;
      nodeMap.forEach((node) => {
        const active = node.id === state.selectedId;
        const hovered = node.id === state.hoveredId;
        const target = active || hovered ? 1.16 : 1;
        node.mesh.scale.set(target, target, target);
        node.material.emissiveIntensity = active
          ? 0.7
          : hovered
            ? 0.42
            : 0.16;
        if (active) {
          const ringMaterial = node.ring.material as THREE.MeshBasicMaterial;
          ringMaterial.opacity =
            0.7 + Math.sin(elapsed * 3.2) * 0.2;
          node.ring.rotation.z = elapsed * 0.45;
        } else {
          const ringMaterial = node.ring.material as THREE.MeshBasicMaterial;
          ringMaterial.opacity = 0;
        }
      });
    };

    const animate = () => {
      const state = stateRef.current;
      const dt = clock.getDelta();
      const elapsed = clock.elapsedTime;

      if (state.playing) {
        group.rotation.y += dt * 0.09 * state.speed;
      } else {
        group.rotation.y += dt * 0.012;
      }

      raycaster.setFromCamera(state.pointerNdc, camera);
      const meshes = Array.from(nodeMap.values()).map(
        (node) => node.mesh,
      );
      const hits = raycaster.intersectObjects(meshes, false);
      const hoveredId = (hits[0]?.object.userData.id as string | undefined) ?? null;
      if (hoveredId !== state.hoveredId) {
        state.hoveredId = hoveredId;
        canvas.style.cursor = hoveredId ? "pointer" : "grab";
      }

      if (state.playing) {
        updateParticles(elapsed * state.speed);
      }
      updateNodes(elapsed);
      updateCamera();
      renderer.render(scene, camera);
    };

    const resize = () => {
      const width = container.clientWidth;
      const height = container.clientHeight;
      if (!width || !height) return;
      renderer.setSize(width, height);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    resize();

    const onPointerDown = (event: PointerEvent) => {
      if (event.pointerType === "mouse" && event.button !== 0) return;
      const state = stateRef.current;
      activePointers.set(event.pointerId, {
        x: event.clientX,
        y: event.clientY,
      });
      if (activePointers.size === 2) {
        const pointers = Array.from(activePointers.values());
        lastPinchDistance = Math.hypot(
          pointers[0].x - pointers[1].x,
          pointers[0].y - pointers[1].y,
        );
      }
      if (activePointers.size === 1) {
        state.pointerDown = true;
        state.pointerMoved = false;
        state.lastX = event.clientX;
        state.lastY = event.clientY;
      }
      container.setPointerCapture?.(event.pointerId);
    };

    const onPointerMove = (event: PointerEvent) => {
      const state = stateRef.current;
      state.pointerNdc.x =
        (event.clientX / container.clientWidth) * 2 - 1;
      state.pointerNdc.y =
        -(event.clientY / container.clientHeight) * 2 + 1;
      if (activePointers.has(event.pointerId)) {
        activePointers.set(event.pointerId, {
          x: event.clientX,
          y: event.clientY,
        });
      }
      if (activePointers.size >= 2) {
        const pointers = Array.from(activePointers.values());
        const distance = Math.hypot(
          pointers[0].x - pointers[1].x,
          pointers[0].y - pointers[1].y,
        );
        if (lastPinchDistance > 0) {
          state.targetRadius = clamp(
            state.targetRadius + (lastPinchDistance - distance) * 0.02,
            6.5,
            16,
          );
        }
        lastPinchDistance = distance;
        return;
      }
      if (!state.pointerDown) return;
      const dx = event.clientX - state.lastX;
      const dy = event.clientY - state.lastY;
      if (Math.abs(dx) + Math.abs(dy) > 3) state.pointerMoved = true;
      state.targetTheta -= dx * 0.006;
      state.targetPhi = clamp(state.targetPhi - dy * 0.006, 0.25, 1.35);
      state.lastX = event.clientX;
      state.lastY = event.clientY;
    };

    const onPointerUp = (event: PointerEvent) => {
      const state = stateRef.current;
      activePointers.delete(event.pointerId);
      if (activePointers.size < 2) lastPinchDistance = 0;
      if (container.hasPointerCapture?.(event.pointerId)) {
        container.releasePointerCapture(event.pointerId);
      }
      if (state.pointerDown && !state.pointerMoved) {
        raycaster.setFromCamera(state.pointerNdc, camera);
        const meshes = Array.from(nodeMap.values()).map(
          (node) => node.mesh,
        );
        const hits = raycaster.intersectObjects(meshes, false);
        const id = hits[0]?.object.userData.id as string | undefined;
        if (id) onStageChange(id);
      }
      state.pointerDown = false;
    };

    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      const state = stateRef.current;
      state.targetRadius = clamp(
        state.targetRadius + event.deltaY * 0.012,
        6.5,
        16,
      );
    };

    container.addEventListener("pointerdown", onPointerDown);
    container.addEventListener("pointermove", onPointerMove);
    container.addEventListener("pointerup", onPointerUp);
    container.addEventListener("pointercancel", onPointerUp);
    container.addEventListener("wheel", onWheel, { passive: false });

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(container);

    let inView = true;
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
      { threshold: 0.08 },
    );
    intersectionObserver.observe(container);
    renderer.setAnimationLoop(animate);

    return () => {
      renderer.setAnimationLoop(null);
      intersectionObserver.disconnect();
      resizeObserver.disconnect();
      container.removeEventListener("pointerdown", onPointerDown);
      container.removeEventListener("pointermove", onPointerMove);
      container.removeEventListener("pointerup", onPointerUp);
      container.removeEventListener("pointercancel", onPointerUp);
      container.removeEventListener("wheel", onWheel);
      nodeMap.clear();
      edgeRigs.length = 0;
      disposables.forEach((item) => item.dispose());
      renderer.dispose();
    };
  }, [onStageChange, reduced, webgl]);

  if (!webgl || reduced) {
    return <SystemFlowDiagram animate={!reduced} />;
  }

  const resetView = () => {
    const state = stateRef.current;
    state.targetTheta = 0.35;
    state.targetPhi = 1.05;
    state.targetRadius = 11;
  };

  const activeStage =
    DEMO_STAGES.find((stage) => stage.id === activeStageId) ?? DEMO_STAGES[0];

  const handleKeyDown = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    const currentIndex = DEMO_STAGES.findIndex(
      (stage) => stage.id === stateRef.current.selectedId,
    );
    if (event.key === "ArrowRight") {
      const next = DEMO_STAGES[(currentIndex + 1) % DEMO_STAGES.length];
      onStageChange(next.id);
    } else if (event.key === "ArrowLeft") {
      const prev =
        DEMO_STAGES[
          (currentIndex - 1 + DEMO_STAGES.length) % DEMO_STAGES.length
        ];
      onStageChange(prev.id);
    } else if (event.key === "Home") {
      onStageChange(DEMO_STAGES[0].id);
    } else if (event.key === "End") {
      onStageChange(DEMO_STAGES[DEMO_STAGES.length - 1].id);
    }
  };

  return (
    <div className="glass-strong p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-bold text-white">3D 系统流程演示</h2>
          <Badge tone="cyan">WebGL</Badge>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={onTogglePlaying}
            aria-label={playing ? "暂停 3D 演示" : "播放 3D 演示"}
          >
            {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
          </Button>
          <div className="glass-inset flex rounded-lg p-0.5">
            {SPEEDS.map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => onSpeedChange(value)}
                className={cn(
                  "focus-ring rounded-md px-2.5 py-1 font-mono text-[11px] font-bold text-slate-500 transition-colors",
                  speed === value && "bg-cyan-400/15 text-accent",
                )}
                aria-pressed={speed === value}
                aria-label={`播放速度 ${value}x`}
              >
                {value}x
              </button>
            ))}
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={resetView}
            aria-label="重置 3D 视角"
          >
            <RotateCcw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div
        ref={containerRef}
        tabIndex={0}
        onKeyDown={handleKeyDown}
        role="application"
        aria-label="3D 系统流程演示，可拖拽、缩放并用方向键切换阶段"
        className="focus-ring relative h-[340px] cursor-grab touch-none overflow-hidden rounded-xl border border-white/10 bg-[#040a13]/70 outline-none sm:h-[420px] active:cursor-grabbing"
      >
        <canvas ref={canvasRef} className="h-full w-full" aria-hidden="true" />
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_42%,rgba(34,211,238,.09),transparent_58%)]" />
        <div className="pointer-events-none absolute bottom-3 left-3 z-10 max-w-[300px] rounded-lg border border-accent/25 bg-[#060d18]/78 p-3 backdrop-blur-md">
          <p className="text-xs font-bold text-accent">{activeStage.label}</p>
          <p className="mt-1 text-[11px] leading-5 text-slate-300">
            {activeStage.description}
          </p>
          <p className="mt-1.5 font-mono text-[10px] text-slate-500">
            {activeStage.metric}
          </p>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {DEMO_STAGES.map((stage, index) => {
          const active = stage.id === activeStageId;
          return (
            <button
              key={stage.id}
              type="button"
              onClick={() => onStageChange(stage.id)}
              aria-pressed={active}
              className={cn(
                "focus-ring inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-[11px] font-semibold transition-all duration-200",
                active
                  ? "border-cyan-300/40 bg-cyan-400/15 text-cyan-100"
                  : "border-white/10 bg-white/[.04] text-slate-400 hover:bg-white/10 hover:text-white",
              )}
            >
              <span className="font-mono text-[10px] text-slate-500">
                0{index + 1}
              </span>
              {stage.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
