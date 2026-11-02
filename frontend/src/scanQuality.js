/**
 * Pure function to derive scan acquisition quality from raw scan statistics.
 * 
 * Engineering quality rules assessing acquisition steadiness:
 * - Good:
 *     coveragePercent >= 80%
 *     agreeingWindows >= 6 (or >= 67% of total windows)
 *     validFrameRatio >= 0.75 (validFrames / observedFrames >= 75%)
 *     status !== 'failed'
 * - Limited:
 *     coveragePercent >= 40%
 *     agreeingWindows >= 2
 *     validFrameRatio >= 0.40
 *     status !== 'failed'
 * - Insufficient:
 *     Below limited thresholds, or status === 'failed', or missing data.
 * 
 * NOTE: Higher scan quality reflects steadier camera conditions and geometric
 * consistency. It does NOT indicate clinical validity or emotional stress accuracy.
 */

export const QUALITY_THRESHOLDS = Object.freeze({
  good: {
    minCoverage: 80,
    minAgreeingWindows: 6,
    minAgreeingFraction: 0.67,
    minValidRatio: 0.75,
  },
  limited: {
    minCoverage: 40,
    minAgreeingWindows: 2,
    minAgreeingFraction: 0.22,
    minValidRatio: 0.40,
  }
});

export function deriveScanQuality({
  coveragePercent = 0,
  agreeingWindows = 0,
  totalWindows = 9,
  validFrames = 0,
  observedFrames = 0,
  status = 'ok'
} = {}) {
  if (status === 'failed' || !observedFrames || observedFrames <= 0) {
    return {
      quality: 'insufficient',
      label: 'Insufficient',
      coveragePercent: Number(coveragePercent) || 0,
      agreeingWindows: Number(agreeingWindows) || 0,
      totalWindows: Number(totalWindows) || 0,
      validFrames: Number(validFrames) || 0,
      observedFrames: Number(observedFrames) || 0,
      validRatio: observedFrames > 0 ? validFrames / observedFrames : 0,
      explanation: 'Acquisition did not capture enough clear frames or landmark consensus.'
    };
  }

  const cov = Number(coveragePercent) || 0;
  const agree = Number(agreeingWindows) || 0;
  const totalW = Math.max(1, Number(totalWindows) || 9);
  const ratio = observedFrames > 0 ? validFrames / observedFrames : 0;
  const agreeFraction = agree / totalW;

  const isGood =
    cov >= QUALITY_THRESHOLDS.good.minCoverage &&
    (agree >= QUALITY_THRESHOLDS.good.minAgreeingWindows || agreeFraction >= QUALITY_THRESHOLDS.good.minAgreeingFraction) &&
    ratio >= QUALITY_THRESHOLDS.good.minValidRatio;

  if (isGood) {
    return {
      quality: 'good',
      label: 'Good',
      coveragePercent: cov,
      agreeingWindows: agree,
      totalWindows: totalW,
      validFrames,
      observedFrames,
      validRatio: ratio,
      explanation: 'Steady acquisition with high coverage, strong window consensus, and clean frame validity.'
    };
  }

  const isLimited =
    cov >= QUALITY_THRESHOLDS.limited.minCoverage &&
    (agree >= QUALITY_THRESHOLDS.limited.minAgreeingWindows || agreeFraction >= QUALITY_THRESHOLDS.limited.minAgreeingFraction) &&
    ratio >= QUALITY_THRESHOLDS.limited.minValidRatio;

  if (isLimited) {
    return {
      quality: 'limited',
      label: 'Limited',
      coveragePercent: cov,
      agreeingWindows: agree,
      totalWindows: totalW,
      validFrames,
      observedFrames,
      validRatio: ratio,
      explanation: 'Acquisition was acceptable but reduced by motion, lighting fluctuations, or lower consensus.'
    };
  }

  return {
    quality: 'insufficient',
    label: 'Insufficient',
    coveragePercent: cov,
    agreeingWindows: agree,
    totalWindows: totalW,
    validFrames,
    observedFrames,
    validRatio: ratio,
    explanation: 'Acquisition did not meet minimum stability thresholds.'
  };
}

