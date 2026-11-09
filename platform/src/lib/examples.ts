// Pilot pieces shown on the landing. Dimensions from data/sample.csv
// (catalogue measures, width × height × depth in cm).

import { formatDimensions } from "@/lib/format";

export interface Example {
  id: string;
  name: string;
  material: string;
  widthCm: number;
  heightCm: number;
  depthCm: number;
  /** Interactive 3D viewer; iOS Quick Look derives the USDZ from the GLB. */
  model?: { glb: string };
}

export const EXAMPLES: readonly Example[] = [
  {
    id: "p15",
    name: "Sillón tapizado",
    material: "Bouclé",
    widthCm: 70,
    heightCm: 77,
    depthCm: 85,
    model: { glb: "/examples/p15.glb" },
  },
  {
    id: "p05",
    name: "Jarrón de gres",
    material: "Gres mate",
    widthCm: 12.5,
    heightCm: 20,
    depthCm: 12,
    model: { glb: "/examples/p05.glb" },
  },
  { id: "p01", name: "Mesa de centro redonda", material: "Madera maciza", widthCm: 50, heightCm: 48.5, depthCm: 50 },
  { id: "p07", name: "Mesa auxiliar", material: "Travertino", widthCm: 35, heightCm: 50, depthCm: 35 },
  { id: "p14", name: "Butaca giratoria", material: "Tapizado", widthCm: 76, heightCm: 81, depthCm: 81 },
  { id: "p02", name: "Jarrón de arcilla", material: "Arcilla envejecida", widthCm: 35, heightCm: 40, depthCm: 35 },
  { id: "p08", name: "Mesita de noche", material: "Madera maciza", widthCm: 52, heightCm: 50, depthCm: 36 },
];

export function photoSrc(id: string): string {
  return `/examples/${id}-foto.jpg`;
}

export function modelSrc(id: string): string {
  return `/examples/${id}-modelo.jpg`;
}

export function exampleDimensions(e: Pick<Example, "widthCm" | "heightCm" | "depthCm">): string {
  return formatDimensions(e.widthCm, e.heightCm, e.depthCm);
}
