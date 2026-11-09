const NBSP = " ";

/** «1000» → «1,000». Digits only (no sign, no decimals): callers add those. */
export function groupThousands(digits: string): string {
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/** «48.5», «1,000»: decimal point, thousands comma, no trailing zeros. */
export function formatCm(value: number): string {
  const [whole, fraction] = String(Number(value)).split(".");
  const grouped = groupThousands(whole);
  return fraction ? `${grouped}.${fraction}` : grouped;
}

/** «50 × 48.5 × 50 cm» (width × height × depth), with a non-breaking space before «cm». */
export function formatDimensions(widthCm: number, heightCm: number, depthCm: number): string {
  return `${formatCm(widthCm)} × ${formatCm(heightCm)} × ${formatCm(depthCm)}${NBSP}cm`;
}
