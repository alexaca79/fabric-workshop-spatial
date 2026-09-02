export const CLASS_LABELS: Record<string, string> = {
  softwood: 'Softwood',
  hardwood: 'Hardwood',
  mixedwood: 'Mixedwood',
  regenerating: 'Regenerating',
  recently_harvested: 'Recently harvested',
  non_forest: 'Non-forest',
  unclassified: 'Unclassified',
};

export const CHANGE_LABELS: Record<string, string> = {
  none: 'No change',
  harvest: 'Harvest',
  disturbance: 'Disturbance',
  moisture_stress: 'Moisture stress',
  regrowth: 'Regrowth',
};

export function hectares(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '\u2014';
  return `${Math.round(value).toLocaleString('en-CA')} ha`;
}

export function percent(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '\u2014';
  return `${(value * 100).toFixed(digits)}%`;
}

export function shortDate(value: Date | string | null | undefined): string {
  if (!value) return '\u2014';
  const date = value instanceof Date ? value : new Date(value);
  return date.toLocaleDateString('en-CA', { year: 'numeric', month: 'short', day: 'numeric' });
}

export function daysAgo(value: Date | string | null | undefined): string {
  if (!value) return 'never';
  const date = value instanceof Date ? value : new Date(value);
  const days = Math.floor((Date.now() - date.getTime()) / 86_400_000);
  if (days <= 0) return 'today';
  if (days === 1) return 'yesterday';
  return `${days} days ago`;
}

/**
 * Coverage below this is worth saying out loud rather than colouring green.
 * A month where two thirds of stands were under cloud is a different month.
 */
export const COVERAGE_FLOOR = 0.7;

export function coverageTone(value: number): 'good' | 'warn' | 'bad' {
  if (value >= COVERAGE_FLOOR) return 'good';
  if (value >= 0.4) return 'warn';
  return 'bad';
}
