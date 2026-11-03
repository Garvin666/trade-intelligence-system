import * as THREE from "three";

import continentParticles from "./continent-particles.json";

interface ContinentParticleRecord {
  x: number;
  y: number;
  z: number;
  brightness: number;
}

const PARTICLES = continentParticles as ContinentParticleRecord[];

export interface ContinentParticlesHandle {
  points: THREE.Points;
  update: (time: number) => void;
  dispose: () => void;
}

export function createContinentParticles(
  radius: number,
  pixelRatio = 2,
): ContinentParticlesHandle {
  const positions = new Float32Array(PARTICLES.length * 3);
  const baseRadius = radius + 0.0065;

  PARTICLES.forEach((particle, index) => {
    positions[index * 3] = particle.x * baseRadius;
    positions[index * 3 + 1] = particle.y * baseRadius;
    positions[index * 3 + 2] = particle.z * baseRadius;
  });

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute(
    "position",
    new THREE.BufferAttribute(positions, 3),
  );

  const material = new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uPixelRatio: { value: pixelRatio },
    },
    vertexShader: `
      uniform float uTime;
      uniform float uPixelRatio;
      varying float vWave;

      void main() {
        vec3 dir = normalize(position);
        float longitude = atan(dir.x, dir.z);
        float wave = sin(longitude * 6.0 + uTime * 0.22) * 0.5 + 0.5;
        wave += 0.1 * sin(longitude * 2.0 - uTime * 0.12);
        wave = clamp(wave, 0.0, 1.0);
        float shapedWave = pow(wave, 0.62);
        vWave = shapedWave;

        float crest = smoothstep(0.16, 0.82, shapedWave);
        float lift = shapedWave * 0.024 + crest * 0.004;
        vec3 pos = position + dir * lift;

        vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
        gl_PointSize = (0.75 + crest * 1.4) * uPixelRatio;
        gl_Position = projectionMatrix * mvPosition;
      }
    `,
    fragmentShader: `
      varying float vWave;

      void main() {
        vec2 uv = gl_PointCoord - 0.5;
        float dist = length(uv);
        float round = 1.0 - smoothstep(0.36, 0.5, dist);

        float crest = smoothstep(0.12, 0.8, vWave);
        float alpha = round * (0.075 + vWave * 0.19);
        if (alpha <= 0.001) discard;

        vec3 deepBlue = vec3(0.13, 0.29, 0.78);
        vec3 brightBlue = vec3(0.22, 0.46, 1.0);
        vec3 color = mix(deepBlue, brightBlue, crest);
        gl_FragColor = vec4(color, alpha);
      }
    `,
    transparent: true,
    depthTest: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });

  const points = new THREE.Points(geometry, material);
  points.frustumCulled = false;
  points.renderOrder = 3;

  return {
    points,
    update(time) {
      material.uniforms.uTime.value = time;
    },
    dispose() {
      geometry.dispose();
      material.dispose();
    },
  };
}
