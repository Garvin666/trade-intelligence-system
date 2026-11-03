import * as THREE from "three";

import nightLightsUrl from "./earth-lights-nasa.jpg";

export interface NightLightsHandle {
  mesh: THREE.Mesh;
  update: (time: number) => void;
  dispose: () => void;
}

export interface NightLightsOptions {
  widthSegments?: number;
  heightSegments?: number;
}

function latLngToPosition(
  lat: number,
  lng: number,
  radius: number,
): [number, number, number] {
  const phi = ((90 - lat) * Math.PI) / 180;
  const theta = ((90 - lng) * Math.PI) / 180;

  return [
    radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta),
  ];
}

function createAlignedSphereGeometry(
  radius: number,
  widthSegments: number,
  heightSegments: number,
): THREE.BufferGeometry {
  const positions: number[] = [];
  const uvs: number[] = [];
  const indices: number[] = [];

  for (let iy = 0; iy <= heightSegments; iy += 1) {
    const lat = 90 - (iy / heightSegments) * 180;
    const v = iy / heightSegments;

    for (let ix = 0; ix <= widthSegments; ix += 1) {
      const lng = -180 + (ix / widthSegments) * 360;
      const u = ix / widthSegments;
      const [x, y, z] = latLngToPosition(lat, lng, radius);

      positions.push(x, y, z);
      uvs.push(u, v);
    }
  }

  for (let iy = 0; iy < heightSegments; iy += 1) {
    for (let ix = 0; ix < widthSegments; ix += 1) {
      const a = iy * (widthSegments + 1) + ix;
      const b = a + widthSegments + 1;

      indices.push(a, b, a + 1, b, b + 1, a + 1);
    }
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute(
    "position",
    new THREE.Float32BufferAttribute(positions, 3),
  );
  geometry.setAttribute("uv", new THREE.Float32BufferAttribute(uvs, 2));
  geometry.setIndex(indices);
  geometry.computeVertexNormals();

  return geometry;
}

export function createNightLights(
  radius: number,
  options: NightLightsOptions = {},
): NightLightsHandle {
  const widthSegments = options.widthSegments ?? 768;
  const heightSegments = options.heightSegments ?? 384;
  const texture = new THREE.TextureLoader().load(nightLightsUrl);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 16;
  texture.generateMipmaps = true;
  texture.minFilter = THREE.LinearMipmapLinearFilter;
  texture.magFilter = THREE.LinearFilter;
  texture.flipY = false;

  const geometry = createAlignedSphereGeometry(
    radius + 0.004,
    widthSegments,
    heightSegments,
  );
  const material = new THREE.ShaderMaterial({
    uniforms: {
      uMap: { value: texture },
      uTime: { value: 0 },
    },
    vertexShader: `
      varying vec2 vUv;

      void main() {
        vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform sampler2D uMap;
      uniform float uTime;
      varying vec2 vUv;

      float hash(vec2 p) {
        return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
      }

      float valueNoise(vec2 p) {
        vec2 i = floor(p);
        vec2 f = fract(p);
        f = f * f * (3.0 - 2.0 * f);

        float a = hash(i);
        float b = hash(i + vec2(1.0, 0.0));
        float c = hash(i + vec2(0.0, 1.0));
        float d = hash(i + vec2(1.0, 1.0));

        return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
      }

      void main() {
        vec4 texel = texture2D(uMap, vUv);
        float lum = max(texel.r, max(texel.g, texel.b));
        float mask = smoothstep(0.04, 0.34, lum);
        float shimmer = 1.0;

        vec3 blueLight = mix(
          vec3(0.2, 0.5, 1.0),
          vec3(0.6, 0.78, 1.0),
          clamp(lum, 0.0, 1.0)
        );

        float alpha = mask * (0.34 + lum * 0.82) * shimmer;
        if (alpha <= 0.001) discard;

        float tintRoll = valueNoise(vUv * vec2(34.0, 17.0));
        vec3 lightColor = blueLight;

        if (tintRoll < 0.16) {
          lightColor = vec3(1.0, 0.92, 0.62) * (0.66 + lum * 0.74);
        } else if (tintRoll > 0.84) {
          lightColor = vec3(0.58, 0.82, 1.0) * (0.62 + lum * 0.72);
        }

        gl_FragColor = vec4(lightColor, alpha);
      }
    `,
    transparent: true,
    depthTest: true,
    depthWrite: false,
    side: THREE.DoubleSide,
    blending: THREE.AdditiveBlending,
  });

  const mesh = new THREE.Mesh(geometry, material);
  mesh.frustumCulled = false;
  mesh.renderOrder = 4;

  return {
    mesh,
    update(time) {
      material.uniforms.uTime.value = time;
    },
    dispose() {
      geometry.dispose();
      material.dispose();
      texture.dispose();
    },
  };
}
