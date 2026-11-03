import * as THREE from "three";

import { MARKET_LOCATIONS, latLngToGlobePosition } from "./markets";

const WAVE_LAYERS = 3;
const WAVE_CYCLE_SECONDS = 5.2;
const WAVE_START_SCALE = 0.022;
const WAVE_END_SCALE = 0.115;
const WAVE_BASE_OPACITY = 0.96;
const MARKER_BLUE = new THREE.Color(0x7dd3fc);
const MARKER_WHITE = new THREE.Color(0xf0f9ff);
const MARKER_DIM = new THREE.Color(0x06152b);
const MARKER_PURPLE = new THREE.Color(0x7e22ce);
const GUANGZHOU = { lat: 23.1291, lng: 113.2644 };
const GUANGZHOU_WAVE_LAYERS = 4;
const GUANGZHOU_CORE_OPACITY = 0.88;
const GUANGZHOU_WAVE_OPACITY = 0.86;
const GUANGZHOU_WAVE_CYCLE_SECONDS = 6.5;

export interface MarketMarkersHandle {
  group: THREE.Group;
  update: (time: number) => void;
  dispose: () => void;
}

interface MarketWaveRecord {
  core: THREE.Sprite;
  waves: THREE.Sprite[];
  phase: number;
  scaleMultiplier: number;
}

function createDiamondCoreTexture(): THREE.CanvasTexture {
  const size = 128;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d")!;

  context.clearRect(0, 0, size, size);

  const diamondGradient = context.createLinearGradient(
    size / 2,
    14,
    size / 2,
    size - 14,
  );
  diamondGradient.addColorStop(0, "rgba(248, 251, 255, 0.94)");
  diamondGradient.addColorStop(0.35, "rgba(186, 230, 253, 0.82)");
  diamondGradient.addColorStop(0.72, "rgba(56, 189, 248, 0.5)");
  diamondGradient.addColorStop(1, "rgba(12, 74, 110, 0.14)");

  context.beginPath();
  context.moveTo(size / 2, 10);
  context.lineTo(size - 12, size / 2);
  context.lineTo(size / 2, size - 10);
  context.lineTo(12, size / 2);
  context.closePath();
  context.fillStyle = diamondGradient;
  context.fill();
  context.strokeStyle = "rgba(224, 242, 254, 0.72)";
  context.lineWidth = 2;
  context.stroke();

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  texture.magFilter = THREE.LinearFilter;
  texture.generateMipmaps = true;
  return texture;
}

function createDiamondWaveTexture(): THREE.CanvasTexture {
  const size = 128;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d")!;

  context.clearRect(0, 0, size, size);

  const drawDiamond = () => {
    context.beginPath();
    context.moveTo(size / 2, 6);
    context.lineTo(size - 6, size / 2);
    context.lineTo(size / 2, size - 6);
    context.lineTo(6, size / 2);
    context.closePath();
  };

  drawDiamond();
  context.strokeStyle = "rgba(125, 211, 252, 0.28)";
  context.lineWidth = 12;
  context.stroke();

  drawDiamond();
  context.strokeStyle = "rgba(186, 230, 253, 0.5)";
  context.lineWidth = 5;
  context.stroke();

  drawDiamond();
  context.strokeStyle = "rgba(224, 242, 254, 0.38)";
  context.lineWidth = 2;
  context.stroke();

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  texture.magFilter = THREE.LinearFilter;
  texture.generateMipmaps = true;
  return texture;
}

function createDimTexture(): THREE.CanvasTexture {
  const size = 128;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d")!;

  context.clearRect(0, 0, size, size);

  const gradient = context.createRadialGradient(
    size / 2,
    size / 2,
    2,
    size / 2,
    size / 2,
    size / 2,
  );
  gradient.addColorStop(0, "rgba(5, 16, 34, 0.96)");
  gradient.addColorStop(0.28, "rgba(8, 24, 48, 0.9)");
  gradient.addColorStop(0.68, "rgba(8, 28, 55, 0.56)");
  gradient.addColorStop(1, "rgba(8, 28, 55, 0)");
  context.fillStyle = gradient;
  context.fillRect(0, 0, size, size);

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  texture.magFilter = THREE.LinearFilter;
  texture.generateMipmaps = true;
  return texture;
}

function createSprite(
  texture: THREE.Texture,
  color: THREE.Color,
  opacity: number,
  size: number,
  renderOrder: number,
): THREE.Sprite {
  const material = new THREE.SpriteMaterial({
    map: texture,
    color,
    transparent: true,
    opacity,
    depthTest: true,
    depthWrite: false,
    blending: THREE.NormalBlending,
  });
  const sprite = new THREE.Sprite(material);
  sprite.scale.setScalar(size);
  sprite.renderOrder = renderOrder;
  return sprite;
}

function waveEnvelope(progress: number): number {
  const fadeIn = Math.max(0, Math.min(1, progress / 0.14));
  const fadeOut = Math.max(0, 1 - progress);
  return fadeIn * fadeOut;
}

export function createMarketMarkers(radius: number): MarketMarkersHandle {
  const group = new THREE.Group();
  group.name = "market-markers";

  const disposables: Array<{ dispose: () => void }> = [];
  const coreTexture = createDiamondCoreTexture();
  const waveTexture = createDiamondWaveTexture();
  const dimTexture = createDimTexture();
  disposables.push(coreTexture, waveTexture, dimTexture);

  const records: MarketWaveRecord[] = [];

  MARKET_LOCATIONS.forEach((market, index) => {
    const position = latLngToGlobePosition(market.lat, market.lng, radius + 0.018);
    const markerGroup = new THREE.Group();
    markerGroup.name = market.id;
    markerGroup.userData.marketId = market.id;
    markerGroup.position.copy(position);
    markerGroup.renderOrder = 8;

    const dim = createSprite(
      dimTexture,
      MARKER_DIM,
      0.78,
      0.125,
      5,
    );
    markerGroup.add(dim);

    const core = createSprite(
      coreTexture,
      MARKER_WHITE,
      0.96,
      0.028,
      9,
    );
    markerGroup.add(core);

    const waves = Array.from({ length: WAVE_LAYERS }, (_, waveIndex) => {
      const wave = createSprite(
        waveTexture,
        MARKER_BLUE,
        0,
        WAVE_START_SCALE,
        8 - waveIndex,
      );
      markerGroup.add(wave);
      return wave;
    });

    group.add(markerGroup);

    records.push({
      core,
      waves,
      phase: (index / MARKET_LOCATIONS.length) * Math.PI * 2,
      scaleMultiplier: 1,
    });

    disposables.push(
      dim.material,
      core.material,
      ...waves.map((wave) => wave.material),
    );
  });

  const guangzhouPosition = latLngToGlobePosition(
    GUANGZHOU.lat,
    GUANGZHOU.lng,
    radius + 0.018,
  );
  const guangzhouGroup = new THREE.Group();
  guangzhouGroup.position.copy(guangzhouPosition);
  guangzhouGroup.renderOrder = 8;
  const outward = guangzhouPosition.clone().normalize();
  guangzhouGroup.quaternion.setFromUnitVectors(
    new THREE.Vector3(0, 0, 1),
    outward,
  );

  const guangzhouCoreGeometry = new THREE.CircleGeometry(1, 64);
  const guangzhouCoreMaterial = new THREE.MeshBasicMaterial({
    color: MARKER_PURPLE,
    transparent: true,
    opacity: GUANGZHOU_CORE_OPACITY,
    depthTest: true,
    depthWrite: false,
    blending: THREE.NormalBlending,
  });
  const guangzhouCore = new THREE.Mesh(
    guangzhouCoreGeometry,
    guangzhouCoreMaterial,
  );
  guangzhouCore.scale.setScalar(0.032);
  guangzhouCore.renderOrder = 10;
  guangzhouGroup.add(guangzhouCore);

  const guangzhouDimGeometry = new THREE.CircleGeometry(1, 64);
  const guangzhouDimMaterial = new THREE.MeshBasicMaterial({
    color: MARKER_DIM,
    transparent: true,
    opacity: 0.72,
    depthTest: true,
    depthWrite: false,
    blending: THREE.NormalBlending,
  });
  const guangzhouDim = new THREE.Mesh(
    guangzhouDimGeometry,
    guangzhouDimMaterial,
  );
  guangzhouDim.scale.setScalar(0.12);
  guangzhouDim.renderOrder = 5;
  guangzhouGroup.add(guangzhouDim);

  const guangzhouWaveGeometry = new THREE.RingGeometry(0.9, 1, 96);
  const guangzhouWaves = Array.from({ length: GUANGZHOU_WAVE_LAYERS }, (_, waveIndex) => {
    const material = new THREE.MeshBasicMaterial({
      color: MARKER_PURPLE,
      transparent: true,
      opacity: 0,
      depthTest: true,
      depthWrite: false,
      side: THREE.DoubleSide,
      blending: THREE.NormalBlending,
    });
    const wave = new THREE.Mesh(guangzhouWaveGeometry, material);
    wave.scale.setScalar(0.024);
    wave.renderOrder = 9 - waveIndex;
    guangzhouGroup.add(wave);
    disposables.push(material);
    return wave;
  });

  group.add(guangzhouGroup);

  disposables.push(
    guangzhouCoreGeometry,
    guangzhouCoreMaterial,
    guangzhouDimGeometry,
    guangzhouDimMaterial,
    guangzhouWaveGeometry,
  );

  return {
    group,
    update(time) {
      records.forEach((record) => {
        const phaseOffset = record.phase * 0.018;

        record.waves.forEach((wave, waveIndex) => {
          const layerOffset = waveIndex / WAVE_LAYERS;
          const progress = ((time / WAVE_CYCLE_SECONDS + phaseOffset + layerOffset) % 1 + 1) % 1;
          const envelope = waveEnvelope(progress);
          const scale = THREE.MathUtils.lerp(
            WAVE_START_SCALE * record.scaleMultiplier,
            WAVE_END_SCALE * record.scaleMultiplier,
            progress,
          );

          wave.scale.setScalar(scale);
          (wave.material as THREE.SpriteMaterial).opacity =
            WAVE_BASE_OPACITY * envelope;
        });
      });

      const guangzhouPhaseOffset = 0.24 * 0.018;
      guangzhouWaves.forEach((wave, waveIndex) => {
        const layerOffset = waveIndex / GUANGZHOU_WAVE_LAYERS;
        const progress = ((time / GUANGZHOU_WAVE_CYCLE_SECONDS + guangzhouPhaseOffset + layerOffset) % 1 + 1) % 1;
        const envelope = waveEnvelope(progress);
        const radius = THREE.MathUtils.lerp(0.024, 0.105, progress);

        wave.scale.setScalar(radius);
        (wave.material as THREE.MeshBasicMaterial).opacity =
          GUANGZHOU_WAVE_OPACITY * envelope;
      });
    },
    dispose() {
      disposables.forEach((item) => item.dispose());
    },
  };
}
