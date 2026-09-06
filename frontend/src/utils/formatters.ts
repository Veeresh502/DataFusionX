/**
 * DataFusionX Centralized Metric Formatting Utilities
 * Enforces safe rendering of numbers, percentages, and memory sizes.
 * Prevents "undefined", "null", "NaN", or "%" alone from rendering in the UI.
 */

export function formatPercentage(val: number | null | undefined, fallback: string = "N/A"): string {
  if (val === null || val === undefined || typeof val !== 'number' || isNaN(val)) {
    return fallback;
  }
  const formatted = val % 1 === 0 ? val.toString() : val.toFixed(2);
  return `${formatted}%`;
}

export function formatNumber(val: number | null | undefined, fallback: string = "N/A"): string {
  if (val === null || val === undefined || typeof val !== 'number' || isNaN(val)) {
    return fallback;
  }
  return val.toLocaleString();
}

export function formatMemoryBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined || typeof bytes !== 'number' || isNaN(bytes)) {
    return "0 KB";
  }
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function getQualityBadgeColor(score: number | null | undefined): string {
  if (score === null || score === undefined || isNaN(score)) return 'text-slate-400 bg-slate-500/10 border-slate-500/20';
  if (score >= 90) return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20';
  if (score >= 70) return 'text-amber-400 bg-amber-500/10 border-amber-500/20';
  return 'text-rose-400 bg-rose-500/10 border-rose-500/20';
}
