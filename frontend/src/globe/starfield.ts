import * as THREE from "three";

import starData from "./star-data.json";

interface StarRecord {
  x: number;
  y: number;
  z: number;
  mag: number;
  ci: number;
}

const STARS = starData as StarRecord[];
const STARFIELD_RADIUS = 100;

const WHITE: [number, number, number] = [0.98, 0.98, 1];
const COOL_WHITE: [number, number, number] = [0.84, 0.92, 1];
const PALE_BLUE: [number, number, number] = [0.66, 0.82, 1];
const PALE_YELLOW: [number, number, number] = [1, 0.9, 0.68];
const WARM_WHITE: [number, number, number] = [1, 0.96, 0.84];

function colorForStar(ci: number, seed: number): [number, number, number] {
  if (ci < 0.05) {
    return seed < 0.9 ? PALE_BLUE : COOL_WHITE;
  }

  if (ci < 0.3) {
    return seed < 0.42 ? COOL_WHITE : WHITE;
  }

  if (ci < 0.6) {
    return seed < 0.08 ? PALE_BLUE : WHITE;
  }

  if (ci < 0.95) {
    return seed < 0.07 ? PALE_YELLOW : WHITE;
  }

  return seed < 0.04 ? WARM_WHITE : WHITE;
}

function createStarfield(pixelRatio = 2): THREE.Points {
  const count = STARS.length;
  const positions = new Float32Array(count * 3);
  const mags = new Float32Array(count);
  const colors = new Float32Array(count * 3);
  const phases = new Float32Array(count);

  for (let i = 0; i < count; i += 1) {
    const star = STARS[i];
    const length = Math.sqrt(
      star.x * star.x + star.y * star.y + star.z * star.z,
    );
    const scale = STARFIELD_RADIUS / length;

    positions[i * 3] = star.x * scale;
    positions[i * 3 + 1] = star.y * scale;
    positions[i * 3 + 2] = star.z * scale;
    mags[i] = star.mag;
    phases[i] = Math.random();

    const [r, g, b] = colorForStar(star.ci, Math.random());
    colors[i * 3] = r;
    colors[i * 3 + 1] = g;
    colors[i * 3 + 2] = b;
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("aMag", new THREE.BufferAttribute(mags, 1));
  geometry.setAttribute("aColor", new THREE.BufferAttribute(colors, 3));
  geometry.setAttribute("aPhase", new THREE.BufferAttribute(phases, 1));

  const material = new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uPixelRatio: { value: pixelRatio },
    },
    vertexShader: `
      attribute float aMag;
      attribute vec3 aColor;
      attribute float aPhase;

      varying vec3 vColor;
      varying float vMag;
      varying float vVisibility;

      uniform float uTime;
      uniform float uPixelRatio;

      void main() {
        float normalized = 1.0 - clamp(aMag / 6.0, 0.0, 1.0);
        float size = mix(0.9, 3.3, pow(normalized, 0.62));

        float faintness = smoothstep(-1.5, 3.5, aMag);
        float twinkleAmount = mix(0.08, 0.2, faintness);
        float frequency = 0.75 + aPhase * 0.85;
        float wave = 0.5 + 0.5 * sin(uTime * frequency + aPhase * 6.2831853);
        float visibility = 1.0 - twinkleAmount * (1.0 - wave);

        gl_PointSize = size * uPixelRatio * (0.9 + normalized * 0.35);
        gl_PointSize *= 0.9 + 0.1 * visibility;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);

        vColor = aColor;
        vMag = aMag;
        vVisibility = visibility;
      }
    `,
    fragmentShader: `
      varying vec3 vColor;
      varying float vMag;
      varying float vVisibility;

      void main() {
        vec2 uv = gl_PointCoord - 0.5;
        float dist = length(uv);
        float edge = 1.0 - smoothstep(0.34, 0.5, dist);
        float core = exp(-dist * 10.0);
        float halo = exp(-dist * 3.0) * edge;
        float brightness = 1.0 - smoothstep(-1.4, 8.0, vMag);
        brightness = pow(brightness, 0.72);
        float alpha = (core + halo * 0.45) * brightness * 1.35;
        alpha *= vVisibility;

        if (alpha <= 0.001) discard;

        vec3 glow = vColor * (1.12 + core * 1.55 + halo * 0.75);
        gl_FragColor = vec4(glow, min(alpha, 1.0));
      }
    `,
    transparent: true,
    depthTest: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });

  const points = new THREE.Points(geometry, material);
  points.frustumCulled = false;
  points.renderOrder = -1;

  return points;
}

export { createStarfield };
