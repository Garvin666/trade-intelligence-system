import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/examples/jsm/postprocessing/OutputPass.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { cn } from "@/shared/lib/utils";
import logoUrl from "@/assets/logo-ship.png?inline";
import { Page3DSceneStatic, type SceneVariant } from "./Page3DSceneStatic";
import { FourQuestionsMark } from "@/shared/brand/FourQuestionsMark";

interface InteractiveMaritimeSceneProps {
  variant?: SceneVariant;
  className?: string;
  height?: number;
  /** 首页全屏旗舰模式；false 时仅渲染紧凑交互视差场景 */
  fullscreen?: boolean;
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

function buildShip(
  group: THREE.Group,
  disposables: Array<{ dispose: () => void }>,
): void {
  const texture = new THREE.TextureLoader().load(logoUrl);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  disposables.push(texture);

  const logoGeo = new THREE.PlaneGeometry(2.35, 2.66);
  const logoMat = new THREE.MeshStandardMaterial({
    map: texture,
    color: 0xe8f8ff,
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    roughness: 0.55,
    metalness: 0.05,
    emissive: 0x6fd9ff,
    emissiveIntensity: 0.3,
  });
  const logo = new THREE.Mesh(logoGeo, logoMat);
  logo.position.set(0, 1.12, 0.12);
  logo.rotation.y = 0.03;
  group.add(logo);

  const haloGeo = new THREE.CircleGeometry(1.5, 48);
  const haloMat = new THREE.MeshBasicMaterial({
    color: 0x22d3ee,
    transparent: true,
    opacity: 0.09,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const halo = new THREE.Mesh(haloGeo, haloMat);
  halo.rotation.x = -Math.PI / 2;
  halo.position.set(0, 0.02, 0.12);
  group.add(halo);
  disposables.push(logoGeo, logoMat, haloGeo, haloMat);
}

function buildRoutes(
  group: THREE.Object3D,
  disposables: Array<{ dispose: () => void }>,
): THREE.Mesh[] {
  const routes: THREE.Mesh[] = [];
  const points: Array<[number, number, number, number]> = [
    [-3.6, 0.18, -0.8, 0x22d3ee],
    [3.4, 0.18, 0.9, 0xd97706],
    [-2.8, 0.18, 1.4, 0x34d399],
    [2.9, 0.18, -1.3, 0x22d3ee],
  ];
  points.forEach(([x, y, z, color]) => {
    const curve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(-3.2, 0.12, -1.6),
      new THREE.Vector3(-1.1, 0.45, -0.3),
      new THREE.Vector3(0, 0.62, 0),
      new THREE.Vector3(1.2, 0.42, 0.35),
      new THREE.Vector3(3.1, 0.12, 1.5),
    ]);
    const geometry = new THREE.TubeGeometry(curve, 40, 0.018, 6, false);
    const material = new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      opacity: 0.32,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.set(x, y, z);
    group.add(mesh);
    routes.push(mesh);
    disposables.push(geometry, material);
  });
  return routes;
}

function buildCompass(
  group: THREE.Group,
  disposables: Array<{ dispose: () => void }>,
): void {
  const ringGeo = new THREE.TorusGeometry(0.9, 0.012, 10, 64);
  const ringMat = new THREE.MeshBasicMaterial({
    color: 0x22d3ee,
    transparent: true,
    opacity: 0.4,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const ring = new THREE.Mesh(ringGeo, ringMat);
  ring.rotation.x = Math.PI / 2.15;
  ring.position.set(0, 2.55, -0.1);
  group.add(ring);

  const nodeGeo = new THREE.SphereGeometry(0.07, 12, 12);
  const nodeColors = [0x22d3ee, 0xd97706, 0x34d399, 0x22d3ee];
  nodeColors.forEach((color, index) => {
    const material = new THREE.MeshBasicMaterial({ color });
    const angle = (index / 4) * Math.PI * 2;
    const node = new THREE.Mesh(nodeGeo, material);
    node.position.set(
      Math.cos(angle) * 0.9,
      2.55 + Math.sin(angle) * 0.22,
      -0.1 + Math.sin(angle) * 0.9,
    );
    group.add(node);
    disposables.push(material);
  });
  disposables.push(ringGeo, ringMat, nodeGeo);
}

export function InteractiveMaritimeScene({
  variant = "default",
  className,
  height,
  fullscreen = false,
}: InteractiveMaritimeSceneProps) {
  const [webgl] = useState(supportsWebGL);
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!webgl || !container || !canvas) return;

    const renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: true,
      powerPreference: "high-performance",
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 0.95;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFShadowMap;

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x060a13, 7, 16);
    const camera = new THREE.PerspectiveCamera(
      52,
      container.clientWidth / Math.max(container.clientHeight, 1),
      0.1,
      40,
    );
    camera.position.set(0, 1.5, 7.4);
    camera.lookAt(0, 0.8, 0);

    const pmrem = new THREE.PMREMGenerator(renderer);
    const envScene = new RoomEnvironment();
    const envMap = pmrem.fromScene(envScene, 0.04).texture;
    scene.environment = envMap;

    scene.add(new THREE.AmbientLight(0xbfd9ff, 0.42));
    const key = new THREE.DirectionalLight(0xdcefff, 1.05);
    key.position.set(4, 6, 3);
    key.castShadow = true;
    key.shadow.mapSize.set(1024, 1024);
    scene.add(key);
    const rim = new THREE.DirectionalLight(0x22d3ee, 0.4);
    rim.position.set(-4, 2, -3);
    scene.add(rim);
    const amber = new THREE.PointLight(0xd97706, 0.3, 8);
    amber.position.set(2.5, 2.2, 1.2);
    scene.add(amber);

    const ship = new THREE.Group();
    ship.position.set(0, 0.45, 0.4);
    scene.add(ship);
    const disposables: Array<{ dispose: () => void }> = [];
    buildShip(ship, disposables);
    const routes = buildRoutes(scene, disposables);
    buildCompass(ship, disposables);

    const oceanGeo = new THREE.PlaneGeometry(
      fullscreen ? 22 : 14,
      fullscreen ? 12 : 8,
      fullscreen ? 72 : 36,
      fullscreen ? 40 : 20,
    );
    oceanGeo.rotateX(-Math.PI / 2);
    const basePositions = Float32Array.from(oceanGeo.attributes.position.array);
    const oceanMat = new THREE.MeshStandardMaterial({
      color: 0x0a1c33,
      roughness: 0.28,
      metalness: 0.55,
      transparent: true,
      opacity: 0.92,
    });
    const ocean = new THREE.Mesh(oceanGeo, oceanMat);
    ocean.position.y = -0.85;
    ocean.receiveShadow = true;
    scene.add(ocean);
    disposables.push(oceanGeo, oceanMat);

    const sparkleGeo = new THREE.BufferGeometry();
    const sparkleCount = fullscreen ? 420 : 120;
    const sparklePositions = new Float32Array(sparkleCount * 3);
    for (let i = 0; i < sparkleCount; i += 1) {
      sparklePositions[i * 3] = (Math.random() - 0.5) * 14;
      sparklePositions[i * 3 + 1] = (Math.random() - 0.5) * 6;
      sparklePositions[i * 3 + 2] = (Math.random() - 0.5) * 8;
    }
    sparkleGeo.setAttribute(
      "position",
      new THREE.BufferAttribute(sparklePositions, 3),
    );
    const sparkleMat = new THREE.PointsMaterial({
      color: 0x7dd3fc,
      size: 0.028,
      transparent: true,
      opacity: 0.34,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const sparkles = new THREE.Points(sparkleGeo, sparkleMat);
    scene.add(sparkles);
    disposables.push(sparkleGeo, sparkleMat);

    const composer = new EffectComposer(renderer);
    composer.addPass(new RenderPass(scene, camera));
    const bloomPass = new UnrealBloomPass(
      new THREE.Vector2(container.clientWidth, container.clientHeight),
      0.18,
      0.45,
      0.85,
    );
    composer.addPass(bloomPass);
    composer.addPass(new OutputPass());

    const timer = new THREE.Timer();
    const pointer = { x: 0, y: 0, tx: 0, ty: 0 };
    const drag = {
      yaw: 0.25,
      pitch: 0.12,
      targetYaw: 0.25,
      targetPitch: 0.12,
      velocity: 0,
      active: false,
      lastX: 0,
      lastY: 0,
      lastT: 0,
    };
    let frameCount = 0;
    let frameTime = 0;
    let qualityDropped = false;
    let inView = true;
    let documentVisible = !document.hidden;

    const resize = () => {
      const width = container.clientWidth;
      const height = container.clientHeight;
      if (!width || !height) return;
      renderer.setSize(width, height);
      composer.setSize(width, height);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    resize();

    const animate = () => {
      const dt = Math.min(timer.getDelta(), 0.05);
      const t = timer.getElapsed();
      const start = performance.now();

      drag.targetYaw += 0.012 * dt;
      drag.targetYaw += 0.02 * dt;
      drag.yaw += (drag.targetYaw - drag.yaw) * Math.min(1, dt * 4);
      drag.pitch += (drag.targetPitch - drag.pitch) * Math.min(1, dt * 4);
      if (drag.active) {
        drag.velocity = 0;
      }
      drag.yaw += drag.velocity * dt;
      drag.yaw = Math.max(-1.25, Math.min(1.25, drag.yaw));
      drag.pitch = Math.max(-0.32, Math.min(0.32, drag.pitch));

      ship.rotation.y = drag.yaw;
      ship.rotation.x = drag.pitch;
      ship.position.y = 0.45 + Math.sin(t * 0.6) * 0.025;

      routes.forEach((route, index) => {
        const material = route.material as THREE.MeshBasicMaterial;
        material.opacity = 0.28 + Math.sin(t * 1.1 + index) * 0.08;
      });

      const pos = oceanGeo.attributes.position.array as Float32Array;
      for (let i = 0; i < pos.length; i += 3) {
        const x = basePositions[i];
        const z = basePositions[i + 2];
        pos[i + 1] =
          Math.sin(x * 0.8 + t * 0.7) * 0.055 +
          Math.cos(z * 0.65 + t * 0.55) * 0.045;
      }
      oceanGeo.attributes.position.needsUpdate = true;
      oceanGeo.computeVertexNormals();

      sparkles.rotation.y += dt * 0.02;
      sparkles.position.y = Math.sin(t * 0.3) * 0.12;

      pointer.x += (pointer.tx - pointer.x) * 0.045;
      pointer.y += (pointer.ty - pointer.y) * 0.045;
      camera.position.x = pointer.x * 0.85;
      camera.position.y = 1.5 - pointer.y * 0.5;
      camera.lookAt(0, 0.8, 0);

      composer.render();

      frameTime += performance.now() - start;
      frameCount += 1;
      if (frameCount >= 90 && !qualityDropped) {
        const avg = frameTime / frameCount;
        if (avg > 22) {
          qualityDropped = true;
          bloomPass.enabled = false;
          renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
          renderer.setSize(container.clientWidth, container.clientHeight);
          composer.setSize(container.clientWidth, container.clientHeight);
        }
      }
    };

    const onPointerDown = (event: PointerEvent) => {
      drag.active = true;
      drag.lastX = event.clientX;
      drag.lastY = event.clientY;
      drag.lastT = performance.now();
      drag.velocity = 0;
      container.setPointerCapture?.(event.pointerId);
    };
    const onPointerMove = (event: PointerEvent) => {
      const rect = container.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      pointer.tx = (event.clientX - rect.left) / rect.width - 0.5;
      pointer.ty = (event.clientY - rect.top) / rect.height - 0.5;
      if (drag.active) {
        const now = performance.now();
        const dx = event.clientX - drag.lastX;
        const dtMs = Math.max(1, now - drag.lastT);
        drag.targetYaw += dx * 0.0045;
        drag.targetPitch = Math.max(
          -0.32,
          Math.min(0.32, drag.targetPitch - (event.clientY - drag.lastY) * 0.003),
        );
        drag.velocity = (dx / dtMs) * 0.006;
        drag.lastX = event.clientX;
      drag.lastY = event.clientY;
      drag.lastT = now;
      }
    };
    const onPointerUp = (event: PointerEvent) => {
      drag.active = false;
      container.releasePointerCapture?.(event.pointerId);
    };
    const onDoubleClick = () => {
      drag.targetYaw = 0.25;
      drag.targetPitch = 0.12;
      drag.velocity = 0;
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onDoubleClick();
    };
    const onVisibility = () => {
      documentVisible = !document.hidden;
      if (!documentVisible || !inView) {
        renderer.setAnimationLoop(null);
      } else {
        renderer.setAnimationLoop(animate);
      }
    };

    container.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    container.addEventListener("dblclick", onDoubleClick);
    window.addEventListener("keydown", onKeyDown);
    document.addEventListener("visibilitychange", onVisibility);
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(container);
    const intersectionObserver = new IntersectionObserver(
      (entries) => {
        inView = entries[0]?.isIntersecting ?? false;
        if (inView && documentVisible) {
          renderer.setAnimationLoop(animate);
        } else {
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
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
      container.removeEventListener("dblclick", onDoubleClick);
      window.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("visibilitychange", onVisibility);
      disposables.forEach((item) => item.dispose());
      oceanGeo.dispose();
      pmrem.dispose();
      composer.dispose();
      renderer.dispose();
    };
  }, [fullscreen, variant, webgl]);

  if (!webgl) {
    return (
      <div
        className={cn(
          fullscreen ? "absolute inset-0" : "relative",
          className,
        )}
        style={height && !fullscreen ? { height } : undefined}
      >
        <Page3DSceneStatic
          height={height ?? (fullscreen ? 520 : 150)}
          variant={variant}
        />
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={cn(
        "relative overflow-hidden bg-base",
        fullscreen ? "absolute inset-0" : "rounded-xl border border-white/10",
        className,
      )}
      style={height && !fullscreen ? { height } : undefined}
      aria-label="远帆号 3D 交互场景"
    >
      <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_40%,rgba(34,211,238,.035),transparent_55%)]" />

      {fullscreen && (
        <>
          <div className="pointer-events-none absolute left-6 top-6 z-10 hidden items-center gap-3 lg:flex">
            <FourQuestionsMark size={40} labelClassName="hidden" className="text-slate-300" />
            <div className="leading-tight">
              <p className="text-sm font-extrabold text-white">远帆智品</p>
              <p className="font-mono text-[10px] tracking-[.18em] text-slate-400 uppercase">
                Precision Trade Terminal
              </p>
            </div>
          </div>

        </>
      )}
    </div>
  );
}
