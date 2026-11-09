const NBSP = " ";

/** «48,5»: decimal comma, no trailing zeros. */
export function formatCm(value: number): string {
  return String(Number(value)).replace(".", ",");
}

/** «50 × 48,5 × 50 cm» (ancho × alto × fondo), with a non-breaking space before «cm». */
export function formatDimensions(widthCm: number, heightCm: number, depthCm: number): string {
  return `${formatCm(widthCm)} × ${formatCm(heightCm)} × ${formatCm(depthCm)}${NBSP}cm`;
}
