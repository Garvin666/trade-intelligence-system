import * as THREE from "three";
import { geoDistance, geoInterpolate } from "d3-geo";

import { MARKET_LOCATIONS, latLngToGlobePosition } from "./markets";

const GUANGZHOU = { lat: 23.1291, lng: 113.2644 };
const CURVE_SEGMENTS = 76;
const DASH_COUNT = 7;
const DASH_SPEED = 0.18;

export interface FlyLinesHandle {
  group: THREE.Group;
  update: (time: number) => void;
  dispose: () => void;
}

function createArcPoints(
  startLat: number,
  startLng: number,
  endLat: number,
  endLng: number,
  radius: number,
): THREE.Vector3[] {
  const interpolate = geoInterpolate([startLng, startLat], [endLng, endLat]);
  const distance = geoDistance([startLng, startLat], [endLng, endLat]);
  const altitude = 0.08 + distance * 0.1;
  const points: THREE.Vector3[] = [];

  for (let index = 0; index <= CURVE_SEGMENTS; index += 1) {
    const t = index / CURVE_SEGMENTS;
    const [lng, lat] = interpolate(t);
    const lift = Math.sin(t * Math.PI) * altitude;
    points.push(latLngToGlobePosition(lat, lng, radius + 0.02 + lift));
  }

  return points;
}

export function createFlyLines(radius: number): FlyLinesHandle {
  const group = new THREE.Group();
  group.name = "fly-lines";

  const geometries: THREE.BufferGeometry[] = [];

  const material = new THREE.ShaderMaterial({
    uniforms: {
      uDashCount: { value: DASH_COUNT },
      uSpeed: { value: DASH_SPEED },
      uTime: { value: 0 },
    },
    vertexShader: `
      attribute float aDistance;
      varying float vDistance;

      void main() {
        vDistance = aDistance;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform float uDashCount;
      uniform float uSpeed;
      uniform float uTime;

      varying float vDistance;

      void main() {
        float phase = fract(vDistance * uDashCount - uTime * uSpeed);
        float dashStart = smoothstep(0.0, 0.12, phase);
        float dashEnd = 1.0 - smoothstep(0.58, 0.62, phase);
        float alpha = dashStart * dashEnd;

        if (alpha <= 0.001) discard;

        gl_FragColor = vec4(vec3(1.0), alpha);
      }
    `,
    transparent: true,
    depthTest: true,
    depthWrite: false,
    blending: THREE.NormalBlending,
  });

  MARKET_LOCATIONS.forEach((market) => {
    const points = createArcPoints(
      GUANGZHOU.lat,
      GUANGZHOU.lng,
      market.lat,
      market.lng,
      radius,
    );
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const distances = new Float32Array(points.length);

    for (let index = 0; index < points.length; index += 1) {
      distances[index] = index / Math.max(1, points.length - 1);
    }

    geometry.setAttribute("aDistance", new THREE.BufferAttribute(distances, 1));
    geometries.push(geometry);

    const line = new THREE.Line(geometry, material);
    line.frustumCulled = false;
    line.renderOrder = 7;
    group.add(line);
  });

  return {
    group,
    update(time) {
      material.uniforms.uTime.value = time;
    },
    dispose() {
      geometries.forEach((geometry) => geometry.dispose());
      material.dispose();
    },
  };
}
