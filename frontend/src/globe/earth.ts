import * as THREE from "three";
import { feature } from "topojson-client";
import GeoJsonGeometry from "three-geojson-geometry";
import ConicPolygonGeometry from "three-conic-polygon-geometry";
import landTopology from "world-atlas/land-110m.json";

export interface EarthHandle {
  group: THREE.Group;
  update: (time: number) => void;
  dispose: () => void;
}

export interface ContinentDepthMaskHandle {
  group: THREE.Group;
  dispose: () => void;
}

const OUTLINE_COLOR = 0x3e70e0;
const SHELL_COLOR = 0x070b24;

type LandGeometry =
  | { type: "Polygon"; coordinates: number[][][] }
  | { type: "MultiPolygon"; coordinates: number[][][][] };

function getLandGeometry(): LandGeometry | undefined {
  const topology = landTopology as unknown as {
    objects: { land: unknown };
  };
  const collection = feature(
    topology as never,
    topology.objects.land as never,
  ) as unknown as {
    features: Array<{
      geometry: LandGeometry;
    }>;
  };

  return collection.features[0]?.geometry;
}

export function createContinentDepthMask(
  radius = 1,
): ContinentDepthMaskHandle {
  const group = new THREE.Group();
  const disposables: Array<{ dispose: () => void }> = [];
  const landGeometry = getLandGeometry();

  if (!landGeometry) {
    return {
      group,
      dispose() {
        disposables.forEach((item) => item.dispose());
      },
    };
  }

  const polygonCoordinates =
    landGeometry.type === "MultiPolygon"
      ? landGeometry.coordinates
      : [landGeometry.coordinates];
  const material = new THREE.MeshBasicMaterial({
    colorWrite: false,
    depthWrite: true,
    depthTest: true,
    side: THREE.DoubleSide,
  });
  disposables.push(material);

  polygonCoordinates.forEach((polygon) => {
    const geometry = new ConicPolygonGeometry(
      polygon,
      radius,
      radius + 0.001,
      false,
      true,
      false,
      3,
    );
    const mesh = new THREE.Mesh(geometry, material);
    mesh.frustumCulled = false;
    mesh.renderOrder = 0;
    group.add(mesh);
    disposables.push(geometry);
  });

  return {
    group,
    dispose() {
      disposables.forEach((item) => item.dispose());
    },
  };
}

export function createEarth(radius = 1): EarthHandle {
  const group = new THREE.Group();
  const disposables: Array<{ dispose: () => void }> = [];
  const landGeometry = getLandGeometry();

  const shellGeometry = new THREE.SphereGeometry(radius * 0.995, 96, 96);
  const shellMaterial = new THREE.MeshBasicMaterial({
    color: SHELL_COLOR,
    transparent: true,
    opacity: 0.26,
    depthWrite: false,
    side: THREE.FrontSide,
  });
  const shell = new THREE.Mesh(shellGeometry, shellMaterial);
  shell.renderOrder = 0;
  group.add(shell);
  disposables.push(shellGeometry, shellMaterial);

  if (landGeometry) {
    const outlineGeometry = new GeoJsonGeometry(
      landGeometry,
      radius + 0.002,
      3,
    );
    const outlineMaterial = new THREE.LineBasicMaterial({
      color: OUTLINE_COLOR,
      transparent: true,
      opacity: 0.3,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const outline = new THREE.LineSegments(outlineGeometry, outlineMaterial);
    outline.renderOrder = 2;
    group.add(outline);
    disposables.push(outlineGeometry, outlineMaterial);
  }

  const atmosphereGeometry = new THREE.SphereGeometry(
    radius * 1.008,
    128,
    128,
  );
  const atmosphereMaterial = new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uColor: { value: new THREE.Color(OUTLINE_COLOR) },
    },
    vertexShader: `
      varying vec3 vNormal;
      varying vec3 vViewPosition;

      void main() {
        vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
        vNormal = normalize(normalMatrix * normal);
        vViewPosition = -mvPosition.xyz;
        gl_Position = projectionMatrix * mvPosition;
      }
    `,
    fragmentShader: `
      uniform float uTime;
      uniform vec3 uColor;

      varying vec3 vNormal;
      varying vec3 vViewPosition;

      void main() {
        vec3 normal = normalize(vNormal);
        vec3 viewDir = normalize(vViewPosition);
        float rim = pow(1.0 - abs(dot(normal, viewDir)), 4.8);
        float flicker = 0.68 + 0.32 * sin(
          uTime * 2.2 + sin(uTime * 1.15) * 0.9
        );
        float alpha = rim * (0.035 + 0.05 * flicker);

        if (alpha <= 0.001) discard;

        gl_FragColor = vec4(uColor * (0.62 + flicker * 0.22), alpha);
      }
    `,
    transparent: true,
    depthWrite: false,
    side: THREE.FrontSide,
    blending: THREE.AdditiveBlending,
  });
  const atmosphere = new THREE.Mesh(atmosphereGeometry, atmosphereMaterial);
  atmosphere.renderOrder = 3;
  group.add(atmosphere);
  disposables.push(atmosphereGeometry, atmosphereMaterial);

  return {
    group,
    update(time) {
      atmosphereMaterial.uniforms.uTime.value = time;
    },
    dispose() {
      disposables.forEach((item) => item.dispose());
    },
  };
}
