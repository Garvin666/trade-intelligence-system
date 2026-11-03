import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { AfterimagePass } from "three/examples/jsm/postprocessing/AfterimagePass.js";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { OutputPass } from "three/examples/jsm/postprocessing/OutputPass.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { ShaderPass } from "three/examples/jsm/postprocessing/ShaderPass.js";
import { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";

import type { GlobePick, GlobePicksMap } from "@/shared/api/types";
import { categoryName } from "@/shared/lib/names";
import { createContinentDepthMask, createEarth } from "./earth";
import { createContinentParticles } from "./continentParticles";
import { createNightLights } from "./nightLights";
import { createStarfield } from "./starfield";
import { createMarketMarkers } from "./marketMarkers";
import { createFlyLines } from "./flyLines";
import {
  MARKET_LOCATIONS,
  type MarketLocation,
  latLngToGlobePosition,
} from "./markets";

const CompositeStarShader = {
  uniforms: {
    tDiffuse: { value: null as THREE.Texture | null },
    tStar: { value: null as THREE.Texture | null },
  },
  vertexShader: `
    varying vec2 vUv;

    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,
  fragmentShader: `
    uniform sampler2D tDiffuse;
    uniform sampler2D tStar;
    varying vec2 vUv;

    void main() {
      vec4 globe = texture2D(tDiffuse, vUv);
      vec4 stars = texture2D(tStar, vUv);
      vec3 color = globe.rgb + stars.rgb;
      gl_FragColor = vec4(color, 1.0);
    }
  `,
};

export type EarthSceneMode = "hero" | "full";

interface EarthSceneProps {
  mode?: EarthSceneMode;
  className?: string;
  onGlobeClick?: () => void;
  onGlobeEnterComplete?: () => void;
  onMarketSelect?: (market: MarketLocation) => void;
  focusMarket?: MarketLocation | null;
  marketPicks?: GlobePicksMap;
}

export default function EarthScene({
  mode = "full",
  className,
  onGlobeClick,
  onGlobeEnterComplete,
  onMarketSelect,
  focusMarket = null,
  marketPicks,
}: EarthSceneProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const overlayRef = useRef<HTMLDivElement | null>(null);
  const modeRef = useRef<EarthSceneMode>(mode);
  const onGlobeClickRef = useRef(onGlobeClick);
  const onGlobeEnterCompleteRef = useRef(onGlobeEnterComplete);
  const onMarketSelectRef = useRef(onMarketSelect);
  const focusMarketRef = useRef<MarketLocation | null>(focusMarket);
  const marketPicksRef = useRef<GlobePicksMap | undefined>(marketPicks);
  const marketCardRefs = useRef<
    Map<
      string,
      {
        card: HTMLButtonElement;
        horizontalLine: SVGLineElement;
        diagonalLine: SVGLineElement;
      }
    >
  >(new Map());
  const marketPickRefs = useRef<
    Map<
      string,
      {
        card: HTMLDivElement;
        horizontalLine: SVGLineElement;
        diagonalLine: SVGLineElement;
        list: HTMLDivElement;
        lastContentKey: string;
      }
    >
  >(new Map());
  const hoveredMarketRef = useRef<string | null>(null);

  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);

  useEffect(() => {
    onGlobeClickRef.current = onGlobeClick;
  }, [onGlobeClick]);

  useEffect(() => {
    onGlobeEnterCompleteRef.current = onGlobeEnterComplete;
  }, [onGlobeEnterComplete]);

  useEffect(() => {
    onMarketSelectRef.current = onMarketSelect;
  }, [onMarketSelect]);

  useEffect(() => {
    focusMarketRef.current = focusMarket;
  }, [focusMarket]);

  useEffect(() => {
    marketPicksRef.current = marketPicks;
  }, [marketPicks]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const marketCards = marketCardRefs.current;
    const marketPicks = marketPickRefs.current;

    const isMobile =
      window.matchMedia("(max-width: 820px)").matches ||
      (navigator.maxTouchPoints > 1 && window.innerWidth < 1024);
    const pixelRatio = Math.min(window.devicePixelRatio, isMobile ? 1.5 : 2);

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      powerPreference: "high-performance",
    });

    renderer.setPixelRatio(pixelRatio);
    renderer.setClearColor(0x000000, 1);
    renderer.domElement.className = "earth-canvas";
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x000000);

    const camera = new THREE.PerspectiveCamera(68, 1, 0.1, 500);
    const chinaLat = 35;
    const chinaLng = 104;
    const initialMode = modeRef.current;
    const heroDistance = 1.58;
    const fullDistance = isMobile ? 4.55 : 3.12;
    const focusDistance = 1.94;
    const initialDistance =
      initialMode === "hero" ? heroDistance : fullDistance;
    const chinaPhi = ((90 - chinaLat) * Math.PI) / 180;
    const chinaTheta = ((90 - chinaLng) * Math.PI) / 180;
    const cameraDirection = new THREE.Vector3(
      Math.sin(chinaPhi) * Math.cos(chinaTheta),
      Math.cos(chinaPhi),
      Math.sin(chinaPhi) * Math.sin(chinaTheta),
    ).normalize();
    camera.position.copy(cameraDirection).multiplyScalar(initialDistance);
    const currentCameraDirection = cameraDirection.clone();
    const targetCameraDirection = cameraDirection.clone();
    const focusAtStart = focusMarketRef.current;
    let focusedMarketAtRest = focusAtStart;
    let rotationSpeed =
      initialMode === "hero" ? 0.08 : focusAtStart ? 0 : 0.05;
    let targetRotationSpeed = rotationSpeed;

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.rotateSpeed = 0.55;
    controls.zoomSpeed = 0.8;
    controls.enablePan = false;
    controls.minDistance = 1.5;
    controls.maxDistance = 6;
    controls.autoRotate = false;
    controls.enabled = initialMode !== "hero";

    const starfield = createStarfield(pixelRatio);
    const starfieldMaterial = starfield.material as THREE.ShaderMaterial;
    scene.add(starfield);

    const continentDepthMask = createContinentDepthMask(1.05);
    scene.add(continentDepthMask.group);

    const globeGroup = new THREE.Group();
    const globeOccluderGeometry = new THREE.SphereGeometry(
      1.05 * 0.985,
      64,
      64,
    );
    const globeOccluderMaterial = new THREE.MeshBasicMaterial({
      colorWrite: false,
      depthWrite: true,
      depthTest: true,
      side: THREE.FrontSide,
    });
    const globeOccluder = new THREE.Mesh(
      globeOccluderGeometry,
      globeOccluderMaterial,
    );
    globeOccluder.frustumCulled = false;
    globeOccluder.renderOrder = 0;
    globeGroup.add(globeOccluder);

    const earth = createEarth(1.05);
    globeGroup.add(earth.group);

    const continentParticles = createContinentParticles(1.05, pixelRatio);
    globeGroup.add(continentParticles.points);

    const nightLights = createNightLights(1.05, {
      widthSegments: isMobile ? 256 : 768,
      heightSegments: isMobile ? 128 : 384,
    });
    globeGroup.add(nightLights.mesh);

    const marketMarkers = createMarketMarkers(1.05);
    globeGroup.add(marketMarkers.group);

    const markerTargets = MARKET_LOCATIONS.map((market) =>
      marketMarkers.group.getObjectByName(market.id),
    ).filter((target): target is THREE.Object3D => target !== undefined);

    const flyLines = createFlyLines(1.05);
    scene.add(globeGroup);

    const flyLineOccluderGeometry = new THREE.SphereGeometry(
      1.05 * 0.985,
      64,
      64,
    );
    const flyLineOccluderMaterial = new THREE.MeshBasicMaterial({
      colorWrite: false,
      depthWrite: true,
      depthTest: true,
    });
    const flyLineOccluder = new THREE.Mesh(
      flyLineOccluderGeometry,
      flyLineOccluderMaterial,
    );
    flyLineOccluder.frustumCulled = false;
    flyLineOccluder.renderOrder = 0;
    flyLines.group.add(flyLineOccluder);
    scene.add(flyLines.group);

    const pointer = new THREE.Vector2();
    const raycaster = new THREE.Raycaster();
    let pointerDown:
      | {
          x: number;
          y: number;
          hit: boolean;
          hitMarketId: string | null;
        }
      | undefined;

    const getMarketIdFromObject = (object: THREE.Object3D): string | null => {
      let current: THREE.Object3D | null = object;

      while (current) {
        const marketId = current.userData?.marketId;
        if (typeof marketId === "string") {
          return marketId;
        }
        current = current.parent;
      }

      return null;
    };

    const onPointerDown = (event: PointerEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);

      const markerIntersections = raycaster.intersectObjects(
        markerTargets,
        true,
      );
      const hitMarketId = markerIntersections[0]
        ? getMarketIdFromObject(markerIntersections[0].object)
        : null;

      pointerDown = {
        x: event.clientX,
        y: event.clientY,
        hit: raycaster.intersectObject(globeGroup, true).length > 0,
        hitMarketId,
      };
    };

    const onPointerUp = (event: PointerEvent) => {
      if (!pointerDown) return;

      const distance = Math.hypot(
        event.clientX - pointerDown.x,
        event.clientY - pointerDown.y,
      );
      const hitMarketId = pointerDown.hitMarketId;
      if (distance < 8) {
        if (hitMarketId) {
          const market = MARKET_LOCATIONS.find(
            (item) => item.id === hitMarketId,
          );
          if (market) {
            onMarketSelectRef.current?.(market);
          }
        } else if (modeRef.current === "hero") {
          if (pointerDown.hit) {
            onGlobeClickRef.current?.();
          }
        } else {
          onGlobeClickRef.current?.();
        }
      }
      pointerDown = undefined;
    };

    const onPointerMove = (event: PointerEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);

      const intersections = raycaster.intersectObjects(markerTargets, true);
      const firstHit = intersections[0];
      hoveredMarketRef.current = firstHit
        ? getMarketIdFromObject(firstHit.object)
        : null;
      renderer.domElement.style.cursor = hoveredMarketRef.current
        ? "pointer"
        : "";
    };

    const onPointerLeave = () => {
      hoveredMarketRef.current = null;
      renderer.domElement.style.cursor = "";
    };

    renderer.domElement.addEventListener("pointerdown", onPointerDown);
    renderer.domElement.addEventListener("pointerup", onPointerUp);
    renderer.domElement.addEventListener("pointermove", onPointerMove);
    renderer.domElement.addEventListener("pointerleave", onPointerLeave);

    const overlay = overlayRef.current;
    if (overlay) {
      overlay.innerHTML = "";

      const lineLayer = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "svg",
      );
      lineLayer.setAttribute("class", "earth-market-lines");
      lineLayer.setAttribute("aria-hidden", "true");

      const cardLayer = document.createElement("div");
      cardLayer.className = "earth-market-card-layer";

      MARKET_LOCATIONS.forEach((market) => {
        const horizontalLine = document.createElementNS(
          "http://www.w3.org/2000/svg",
          "line",
        );
        horizontalLine.setAttribute("class", "earth-market-line");
        horizontalLine.setAttribute("x1", "0");
        horizontalLine.setAttribute("y1", "0");
        horizontalLine.setAttribute("x2", "0");
        horizontalLine.setAttribute("y2", "0");

        const diagonalLine = document.createElementNS(
          "http://www.w3.org/2000/svg",
          "line",
        );
        diagonalLine.setAttribute("class", "earth-market-line");
        diagonalLine.setAttribute("x1", "0");
        diagonalLine.setAttribute("y1", "0");
        diagonalLine.setAttribute("x2", "0");
        diagonalLine.setAttribute("y2", "0");

        lineLayer.append(horizontalLine, diagonalLine);

        const card = document.createElement("button");
        card.type = "button";
        card.className = "earth-market-card";
        card.dataset.marketId = market.id;

        const city = document.createElement("span");
        city.className = "earth-market-card-city";
        city.textContent = market.city;

        const region = document.createElement("span");
        region.className = "earth-market-card-region";
        region.textContent = market.label;

        card.append(city, region);
        card.addEventListener("click", () => {
          onMarketSelectRef.current?.(market);
        });
        cardLayer.append(card);
        marketCards.set(market.id, {
          card,
          horizontalLine,
          diagonalLine,
        });
      });

      overlay.append(lineLayer, cardLayer);

      const picksLayer = document.createElement("div");
      picksLayer.className = "earth-market-picks-layer";

      MARKET_LOCATIONS.forEach((market) => {
        const horizontalLine = document.createElementNS(
          "http://www.w3.org/2000/svg",
          "line",
        );
        horizontalLine.setAttribute(
          "class",
          "earth-market-line earth-market-picks-line",
        );
        horizontalLine.setAttribute("x1", "0");
        horizontalLine.setAttribute("y1", "0");
        horizontalLine.setAttribute("x2", "0");
        horizontalLine.setAttribute("y2", "0");

        const diagonalLine = document.createElementNS(
          "http://www.w3.org/2000/svg",
          "line",
        );
        diagonalLine.setAttribute(
          "class",
          "earth-market-line earth-market-picks-line",
        );
        diagonalLine.setAttribute("x1", "0");
        diagonalLine.setAttribute("y1", "0");
        diagonalLine.setAttribute("x2", "0");
        diagonalLine.setAttribute("y2", "0");

        lineLayer.append(horizontalLine, diagonalLine);

        const card = document.createElement("div");
        card.className = "earth-market-picks";
        card.dataset.marketId = market.id;

        const title = document.createElement("div");
        title.className = "earth-market-picks-title";

        const city = document.createElement("span");
        city.className = "earth-market-picks-city";
        city.textContent = market.city;

        const region = document.createElement("span");
        region.className = "earth-market-picks-region";
        region.textContent = market.label;

        title.append(city, region);

        const list = document.createElement("div");
        list.className = "earth-market-picks-list";

        card.append(title, list);
        picksLayer.append(card);
        marketPicks.set(market.id, {
          card,
          horizontalLine,
          diagonalLine,
          list,
          lastContentKey: "",
        });
      });

      overlay.append(picksLayer);
    }

    if (import.meta.env.DEV) {
      (
        window as typeof window & {
          __tradeEarthSceneDebug?: {
            hitTest: (clientX: number, clientY: number) => boolean;
            getGlobeScreenPosition: () => {
              x: number;
              y: number;
              top: number;
            };
            getState: () => {
              mode: EarthSceneMode;
              controlsEnabled: boolean;
              cameraPosition: [number, number, number];
              globePosition: [number, number, number];
              heroViewOffset: number;
            };
            getOriginScreenPosition: () => {
              x: number;
              y: number;
            };
          };
        }
      ).__tradeEarthSceneDebug = {
        hitTest(clientX, clientY) {
          const rect = renderer.domElement.getBoundingClientRect();
          pointer.x = ((clientX - rect.left) / rect.width) * 2 - 1;
          pointer.y = -((clientY - rect.top) / rect.height) * 2 + 1;
          raycaster.setFromCamera(pointer, camera);
          return raycaster.intersectObject(globeGroup, true).length > 0;
        },
        getGlobeScreenPosition() {
          const worldPosition = new THREE.Vector3();
          globeGroup.getWorldPosition(worldPosition);
          worldPosition.project(camera);
          const rect = renderer.domElement.getBoundingClientRect();
          return {
            x: (worldPosition.x * 0.5 + 0.5) * rect.width,
            y: (-worldPosition.y * 0.5 + 0.5) * rect.height,
            top: rect.top,
          };
        },
        getState() {
          return {
            mode: modeRef.current,
            controlsEnabled: controls.enabled,
            cameraPosition: camera.position.toArray() as [number, number, number],
            globePosition: globeGroup.position.toArray() as [number, number, number],
            heroViewOffset:
              modeRef.current === "hero"
                ? -container.clientWidth * 0.5
                : 0,
          };
        },
        getOriginScreenPosition() {
          const origin = new THREE.Vector3(0, 0, 0);
          origin.project(camera);
          const rect = renderer.domElement.getBoundingClientRect();
          return {
            x: (origin.x * 0.5 + 0.5) * rect.width,
            y: (-origin.y * 0.5 + 0.5) * rect.height,
          };
        },
      };
    }

    const starTarget = new THREE.WebGLRenderTarget(1, 1);
    const starComposer = new EffectComposer(renderer, starTarget);
    starComposer.renderToScreen = false;
    starComposer.setPixelRatio(renderer.getPixelRatio());
    starComposer.addPass(
      new RenderPass(scene, camera, null, new THREE.Color(0x000000), 1),
    );

    const starBloomPass = new UnrealBloomPass(
      new THREE.Vector2(window.innerWidth, window.innerHeight),
      0.36,
      0.4,
      0.72,
    );
    starComposer.addPass(starBloomPass);

    const afterimagePass = new AfterimagePass(0);
    starComposer.addPass(afterimagePass);

    const globeComposer = new EffectComposer(renderer);
    globeComposer.setPixelRatio(renderer.getPixelRatio());
    globeComposer.addPass(
      new RenderPass(scene, camera, null, new THREE.Color(0x000000), 0),
    );

    const globeBloomPass = new UnrealBloomPass(
      new THREE.Vector2(window.innerWidth, window.innerHeight),
      0.36,
      0.4,
      0.72,
    );
    globeComposer.addPass(globeBloomPass);

    const compositePass = new ShaderPass(CompositeStarShader);
    globeComposer.addPass(compositePass);
    globeComposer.addPass(new OutputPass());

    let trailTarget = 0;
    const enableTrails = () => {
      trailTarget = 0.92;
    };
    const disableTrails = () => {
      trailTarget = 0;
    };

    controls.addEventListener("start", enableTrails);
    controls.addEventListener("end", disableTrails);

    const updateSize = () => {
      const width = container.clientWidth || window.innerWidth;
      const height = container.clientHeight || window.innerHeight;

      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
      starComposer.setSize(width, height);
      globeComposer.setSize(width, height);
      starBloomPass.setSize(width, height);
      globeBloomPass.setSize(width, height);
    };

    const resizeObserver = new ResizeObserver(updateSize);
    resizeObserver.observe(container);
    updateSize();

    const initialViewportWidth =
      container.clientWidth || window.innerWidth;
    let currentDistance = initialDistance;
    let currentViewOffsetX =
      initialMode === "hero" ? -initialViewportWidth * 0.5 : 0;
    let currentMode = initialMode;
    let targetMode = initialMode;
    let transition = {
      active: false,
      start: 0,
      duration: 0,
      fromDistance: initialDistance,
      toDistance: initialDistance,
      fromViewOffsetX: currentViewOffsetX,
      toViewOffsetX: currentViewOffsetX,
      fromDirection: currentCameraDirection.clone(),
      toDirection: targetCameraDirection.clone(),
      notifyComplete: false,
    };

    const easeInOutCubic = (value: number) =>
      value < 0.5
        ? 4 * value * value * value
        : 1 - Math.pow(-2 * value + 2, 3) / 2;

    const getMarketId = (market: MarketLocation | null) => market?.id ?? null;

    const startModeTransition = (
      nextMode: EarthSceneMode,
      now: number,
      focusOverride?: MarketLocation | null,
    ) => {
      const focusMarket =
        focusOverride !== undefined ? focusOverride : focusMarketRef.current;
      const focusChanged =
        getMarketId(focusMarket) !== getMarketId(focusedMarketAtRest);

      if (
        nextMode === currentMode &&
        !transition.active &&
        !focusChanged
      ) {
        return;
      }

      const width = container.clientWidth || window.innerWidth;
      const wasHeroToFull = currentMode === "hero" && nextMode === "full";
      const nextDirection = cameraDirection.clone();

      if (nextMode === "full" && focusMarket) {
        nextDirection.copy(
          latLngToGlobePosition(focusMarket.lat, focusMarket.lng, 1)
            .applyQuaternion(globeGroup.quaternion)
            .normalize(),
        );
      }

      targetMode = nextMode;
      targetRotationSpeed =
        nextMode === "hero" ? 0.08 : focusMarket ? 0 : 0.05;
      transition = {
        active: true,
        start: now,
        duration:
          nextMode === "full"
            ? isMobile
              ? 760
              : 900
            : isMobile
              ? 640
              : 720,
        fromDistance: currentDistance,
        toDistance:
          nextMode === "hero"
            ? heroDistance
            : focusMarket
              ? focusDistance
              : fullDistance,
        fromViewOffsetX: currentViewOffsetX,
        toViewOffsetX: nextMode === "hero" ? -width * 0.5 : 0,
        fromDirection: currentCameraDirection.clone(),
        toDirection: nextDirection,
        notifyComplete: wasHeroToFull,
      };
    };

    const updateModeTransition = (now: number) => {
      if (!transition.active) return;

      const progress = Math.min(
        1,
        (now - transition.start) / transition.duration,
      );
      const eased = easeInOutCubic(progress);
      currentDistance =
        transition.fromDistance +
        (transition.toDistance - transition.fromDistance) * eased;
      currentViewOffsetX =
        transition.fromViewOffsetX +
        (transition.toViewOffsetX - transition.fromViewOffsetX) * eased;

      if (targetMode === "full" && focusMarketRef.current) {
        transition.toDirection.copy(
          latLngToGlobePosition(
            focusMarketRef.current.lat,
            focusMarketRef.current.lng,
            1,
          )
            .applyQuaternion(globeGroup.quaternion)
            .normalize(),
        );
      }

      currentCameraDirection
        .lerpVectors(transition.fromDirection, transition.toDirection, eased)
        .normalize();
      camera.position.copy(currentCameraDirection).multiplyScalar(currentDistance);

      if (progress >= 1) {
        currentDistance = transition.toDistance;
        currentViewOffsetX = transition.toViewOffsetX;
        currentCameraDirection.copy(transition.toDirection);
        targetCameraDirection.copy(transition.toDirection);
        transition.active = false;
        currentMode = targetMode;
        focusedMarketAtRest = focusMarketRef.current;

        if (transition.notifyComplete) {
          transition.notifyComplete = false;
          onGlobeEnterCompleteRef.current?.();
        }
      }
    };

    const CARD_WIDTH = 126;
    const CARD_HEIGHT = 46;
    const PICKS_WIDTH = 272;
    const PICKS_HEIGHT = 220;
    const HERO_VIEW_TOP = 64;
    const markerWorldPosition = new THREE.Vector3();
    const markerScreenPosition = new THREE.Vector3();

    const updatePickContent = (
      elements: { list: HTMLDivElement; lastContentKey: string },
      picks: GlobePick[],
      loading = false,
    ) => {
      const signature = picks
        .map(
          (pick) =>
            `${pick.category}|${pick.six_dimension_score}|${pick.verdict}|${pick.forecast_growth}`,
        )
        .join(",");
      if (elements.lastContentKey === signature) return;
      elements.lastContentKey = signature;
      elements.list.innerHTML = "";

      if (picks.length === 0) {
        const empty = document.createElement("div");
        empty.className = "earth-market-picks-empty";
        empty.textContent = loading ? "选品加载中…" : "暂无推荐选品";
        elements.list.append(empty);
        return;
      }

      picks.slice(0, 4).forEach((pick, index) => {
        const row = document.createElement("div");
        row.className = "earth-market-pick-row";

        const rank = document.createElement("span");
        rank.className = "earth-market-pick-rank";
        rank.textContent = String(index + 1);

        const main = document.createElement("div");
        main.className = "earth-market-pick-main";

        const name = document.createElement("span");
        name.className = "earth-market-pick-name";
        name.textContent = pick.category_name || categoryName(pick.category);

        const meta = document.createElement("span");
        meta.className = "earth-market-pick-meta";
        const growthPrefix = pick.forecast_growth >= 0 ? "+" : "";
        meta.textContent = `${pick.verdict || "推荐"} · 增长 ${growthPrefix}${pick.forecast_growth.toFixed(1)}%`;

        main.append(name, meta);

        const score = document.createElement("span");
        score.className = "earth-market-pick-score";
        score.textContent = pick.six_dimension_score.toFixed(1);

        row.append(rank, main, score);
        elements.list.append(row);
      });
    };

    const updateMarketOverlay = () => {
      if (!overlay) return;

      const width = container.clientWidth || window.innerWidth;
      const height = container.clientHeight || window.innerHeight;
      const screenPositions = new Map<string, { x: number; y: number }>();
      const visibleTop = targetMode === "hero" ? HERO_VIEW_TOP : 0;

      markerTargets.forEach((target, index) => {
        const market = MARKET_LOCATIONS[index];
        if (!market) return;

        target.getWorldPosition(markerWorldPosition);
        markerScreenPosition.copy(markerWorldPosition).project(camera);

        const isInFrontOfCamera =
          markerScreenPosition.z < 1 && markerScreenPosition.z > -1;
        const isFacingCamera =
          markerWorldPosition.dot(camera.position) >
          markerWorldPosition.lengthSq();
        const isFront = isInFrontOfCamera && isFacingCamera;
        const x = (markerScreenPosition.x * 0.5 + 0.5) * width;
        const y = (-markerScreenPosition.y * 0.5 + 0.5) * height;

        if (
          isFront &&
          x >= 0 &&
          x <= width &&
          y >= visibleTop &&
          y <= height
        ) {
          screenPositions.set(market.id, { x, y });
        }
      });

      const activeIds = new Set<string>();
      const hoveredMarket = hoveredMarketRef.current;
      if (hoveredMarket && screenPositions.has(hoveredMarket)) {
        activeIds.add(hoveredMarket);
      }

      const activeMarkets = MARKET_LOCATIONS.filter(
        (market) =>
          activeIds.has(market.id) && screenPositions.has(market.id),
      );
      const placedCards: Array<{
        id: string;
        markerX: number;
        markerY: number;
        cardX: number;
        cardY: number;
      }> = [];
      const placedPicks: Array<{
        id: string;
        markerX: number;
        markerY: number;
        cardX: number;
        cardY: number;
      }> = [];

      const placeMarketPicks = (market: MarketLocation, topOffset: number) => {
        const position = screenPositions.get(market.id);
        if (!position) return;

        const markerX = position.x;
        const markerY = position.y;
        let cardX = markerX + 48;

        if (cardX + PICKS_WIDTH > width - 12) {
          cardX = markerX - PICKS_WIDTH - 48;
        }
        cardX = Math.max(12, Math.min(width - PICKS_WIDTH - 12, cardX));

        const cardY = Math.max(
          topOffset,
          Math.min(height - PICKS_HEIGHT - 12, markerY - PICKS_HEIGHT / 2),
        );

        const picksMap = marketPicksRef.current;
        const picks = picksMap?.[market.id] ?? [];
        const elements = marketPicks.get(market.id);
        if (elements) {
          updatePickContent(elements, picks, picksMap === undefined);
        }

        placedPicks.push({
          id: market.id,
          markerX,
          markerY,
          cardX,
          cardY,
        });
      };

      activeMarkets.forEach((market) => {
        placeMarketPicks(market, targetMode === "hero" ? visibleTop + 12 : 12);
      });

      MARKET_LOCATIONS.forEach((market) => {
        const elements = marketCards.get(market.id);
        if (!elements) return;

        const placed = placedCards.find((item) => item.id === market.id);
        if (!placed) {
          elements.card.classList.remove("is-visible");
          elements.card.style.pointerEvents = "none";
          elements.card.setAttribute("aria-hidden", "true");
          elements.card.tabIndex = -1;
          elements.horizontalLine.style.opacity = "0";
          elements.diagonalLine.style.opacity = "0";
          return;
        }

        elements.card.classList.add("is-visible");
        elements.card.style.pointerEvents = "auto";
        elements.card.setAttribute("aria-hidden", "false");
        elements.card.tabIndex = 0;
        elements.card.style.left = `${placed.cardX}px`;
        elements.card.style.top = `${placed.cardY}px`;

        const horizontalEndX = placed.markerX - 48;
        const lineEndX =
          placed.markerX < placed.cardX
            ? placed.cardX
            : placed.cardX + CARD_WIDTH;
        const lineEndY = placed.cardY + CARD_HEIGHT / 2;

        elements.horizontalLine.setAttribute("x1", String(placed.markerX));
        elements.horizontalLine.setAttribute("y1", String(placed.markerY));
        elements.horizontalLine.setAttribute("x2", String(horizontalEndX));
        elements.horizontalLine.setAttribute("y2", String(placed.markerY));
        elements.horizontalLine.style.opacity = "1";

        elements.diagonalLine.setAttribute("x1", String(horizontalEndX));
        elements.diagonalLine.setAttribute("y1", String(placed.markerY));
        elements.diagonalLine.setAttribute("x2", String(lineEndX));
        elements.diagonalLine.setAttribute("y2", String(lineEndY));
        elements.diagonalLine.style.opacity = "1";
      });

      MARKET_LOCATIONS.forEach((market) => {
        const elements = marketPicks.get(market.id);
        if (!elements) return;

        const placed = placedPicks.find((item) => item.id === market.id);
        if (!placed) {
          elements.card.classList.remove("is-visible");
          elements.horizontalLine.style.opacity = "0";
          elements.diagonalLine.style.opacity = "0";
          return;
        }

        elements.card.classList.add("is-visible");
        elements.card.style.left = `${placed.cardX}px`;
        elements.card.style.top = `${placed.cardY}px`;

        const horizontalEndX =
          placed.markerX + (placed.markerX < placed.cardX ? 44 : -44);
        const lineEndX =
          placed.markerX < placed.cardX
            ? placed.cardX
            : placed.cardX + PICKS_WIDTH;
        const lineEndY = placed.cardY + PICKS_HEIGHT / 2;

        elements.horizontalLine.setAttribute("x1", String(placed.markerX));
        elements.horizontalLine.setAttribute("y1", String(placed.markerY));
        elements.horizontalLine.setAttribute("x2", String(horizontalEndX));
        elements.horizontalLine.setAttribute("y2", String(placed.markerY));
        elements.horizontalLine.style.opacity = "1";

        elements.diagonalLine.setAttribute("x1", String(horizontalEndX));
        elements.diagonalLine.setAttribute("y1", String(placed.markerY));
        elements.diagonalLine.setAttribute("x2", String(lineEndX));
        elements.diagonalLine.setAttribute("y2", String(lineEndY));
        elements.diagonalLine.style.opacity = "1";
      });
    };

    let previousTime = performance.now();
    let elapsedTime = 0;

    renderer.setAnimationLoop(() => {
      const now = performance.now();
      const delta = Math.min((now - previousTime) / 1000, 0.1);
      previousTime = now;
      elapsedTime += delta;

      const desiredMode = modeRef.current;
      if (desiredMode !== targetMode) {
        startModeTransition(desiredMode, now);
      }

      const focusMarket = focusMarketRef.current;
      if (
        targetMode === "full" &&
        getMarketId(focusMarket) !== getMarketId(focusedMarketAtRest) &&
        !transition.active
      ) {
        startModeTransition("full", now, focusMarket);
      }

      updateModeTransition(now);

      controls.enabled = targetMode !== "hero" && !transition.active;
      controls.update();
      camera.updateMatrixWorld();

      targetRotationSpeed =
        targetMode === "hero" ? 0.08 : focusMarket ? 0 : 0.05;
      rotationSpeed +=
        (targetRotationSpeed - rotationSpeed) * Math.min(1, delta * 6);
      globeGroup.rotation.y += delta * rotationSpeed;
      starfieldMaterial.uniforms.uTime.value = elapsedTime;
      earth.update(elapsedTime);
      continentParticles.update(elapsedTime);
      nightLights.update(elapsedTime);
      marketMarkers.update(elapsedTime);
      flyLines.update(elapsedTime);
      const currentDamp = afterimagePass.damp;
      afterimagePass.damp +=
        (trailTarget - currentDamp) * Math.min(1, delta * 8);

      globeGroup.updateMatrixWorld(true);

      const width = container.clientWidth || window.innerWidth;
      const height = container.clientHeight || window.innerHeight;

      if (!transition.active) {
        currentViewOffsetX = targetMode === "hero" ? -width * 0.5 : 0;
      }

      camera.clearViewOffset();
      camera.updateProjectionMatrix();
      starfield.visible = true;
      globeGroup.visible = false;
      flyLines.group.visible = false;
      continentDepthMask.group.visible = true;
      starComposer.render();
      compositePass.uniforms.tStar.value = starComposer.readBuffer.texture;

      if (Math.abs(currentViewOffsetX) > 0.5) {
        camera.setViewOffset(
          width,
          height,
          currentViewOffsetX,
          0,
          width,
          height,
        );
        camera.updateProjectionMatrix();
      }

      updateMarketOverlay();

      flyLines.group.rotation.copy(globeGroup.rotation);
      flyLines.group.visible = true;
      starfield.visible = false;
      globeGroup.visible = true;
      continentDepthMask.group.visible = false;
      globeComposer.render();
    });

    return () => {
      resizeObserver.disconnect();
      renderer.setAnimationLoop(null);
      controls.removeEventListener("start", enableTrails);
      controls.removeEventListener("end", disableTrails);
      renderer.domElement.removeEventListener("pointerdown", onPointerDown);
      renderer.domElement.removeEventListener("pointerup", onPointerUp);
      renderer.domElement.removeEventListener("pointermove", onPointerMove);
      renderer.domElement.removeEventListener("pointerleave", onPointerLeave);
      if (overlay) {
        overlay.innerHTML = "";
      }
      marketCards.clear();
      marketPicks.clear();
      controls.dispose();
      starBloomPass.dispose();
      afterimagePass.dispose();
      globeBloomPass.dispose();
      starTarget.dispose();
      globeOccluderGeometry.dispose();
      globeOccluderMaterial.dispose();
      earth.dispose();
      continentDepthMask.dispose();
      continentParticles.dispose();
      nightLights.dispose();
      marketMarkers.dispose();
      flyLines.dispose();
      flyLineOccluderGeometry.dispose();
      flyLineOccluderMaterial.dispose();
      starfield.geometry.dispose();
      (starfield.material as THREE.ShaderMaterial).dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className={`earth-scene ${className ?? ""}`}
    >
      <div ref={overlayRef} className="earth-market-overlay" />
    </div>
  );
}
