import * as THREE from "three";

export interface MarketLocation {
  id: string;
  label: string;
  city: string;
  lat: number;
  lng: number;
}

export const MARKET_LOCATIONS: MarketLocation[] = [
  { id: "us", label: "美国", city: "纽约", lat: 40.7128, lng: -74.006 },
  { id: "eu", label: "欧洲", city: "布鲁塞尔", lat: 50.8503, lng: 4.3517 },
  { id: "sea", label: "东南亚", city: "新加坡", lat: 1.3521, lng: 103.8198 },
  { id: "jp", label: "日本", city: "东京", lat: 35.6762, lng: 139.6503 },
  { id: "ca", label: "加拿大", city: "多伦多", lat: 43.6532, lng: -79.3832 },
  { id: "au", label: "澳大利亚", city: "悉尼", lat: -33.8688, lng: 151.2093 },
  { id: "uk", label: "英国", city: "伦敦", lat: 51.5074, lng: -0.1278 },
  { id: "kr", label: "韩国", city: "首尔", lat: 37.5665, lng: 126.978 },
  { id: "de", label: "德国", city: "柏林", lat: 52.52, lng: 13.405 },
  { id: "fr", label: "法国", city: "巴黎", lat: 48.8566, lng: 2.3522 },
  { id: "vn", label: "越南", city: "胡志明市", lat: 10.8231, lng: 106.6297 },
  { id: "ru", label: "俄罗斯", city: "莫斯科", lat: 55.7558, lng: 37.6173 },
  { id: "hu", label: "匈牙利", city: "布达佩斯", lat: 47.4979, lng: 19.0402 },
  { id: "ae", label: "中东", city: "迪拜", lat: 25.2048, lng: 55.2708 },
  { id: "mx", label: "墨西哥", city: "墨西哥城", lat: 19.4326, lng: -99.1332 },
];

export function latLngToGlobePosition(
  lat: number,
  lng: number,
  radius: number,
): THREE.Vector3 {
  const phi = ((90 - lat) * Math.PI) / 180;
  const theta = ((90 - lng) * Math.PI) / 180;

  return new THREE.Vector3(
    radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta),
  );
}

export function randomDirectionInHemisphere(
  normal: THREE.Vector3,
  random: () => number = Math.random,
): THREE.Vector3 {
  const up = new THREE.Vector3(0, 1, 0);
  if (Math.abs(normal.dot(up)) > 0.98) {
    up.set(1, 0, 0);
  }

  const tangent = new THREE.Vector3().crossVectors(up, normal).normalize();
  const bitangent = new THREE.Vector3().crossVectors(normal, tangent).normalize();
  const alongNormal = random();
  const angle = random() * Math.PI * 2;
  const radial = Math.sqrt(Math.max(0, 1 - alongNormal * alongNormal));

  return normal
    .clone()
    .multiplyScalar(alongNormal)
    .addScaledVector(tangent, radial * Math.cos(angle))
    .addScaledVector(bitangent, radial * Math.sin(angle))
    .normalize();
}
