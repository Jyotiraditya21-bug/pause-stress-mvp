/**
 * History Insights calculations for compatible scan groups.
 * Real metrics derived strictly from the user's saved scans.
 */

function quantile(values, q) {
  if (!values.length) return null;
  const a = [...values].sort((x, y) => x - y);
  const p = (a.length - 1) * q;
  const i = Math.floor(p);
  return a[i] + (a[Math.min(i + 1, a.length - 1)] - a[i]) * (p - i);
}

export function median(values) {
  return quantile(values, 0.5);
}

export function mad(values) {
  if (!values.length) return null;
  const m = median(values);
  return median(values.map(v => Math.abs(v - m)));
}

export function computeGroupInsights(rows = []) {
  if (!rows || !rows.length) return null;

  const validRows = rows.filter(r => Number.isFinite(r.average));
  const sorted = [...rows].sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at));

  // 1. Scans saved, days with at least one scan, date range
  const scansSaved = rows.length;
  const daysSet = new Set(
    rows.map(r => {
      const d = new Date(r.created_at);
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    })
  );
  const daysWithScans = daysSet.size;

  const startMs = Date.parse(sorted[0].created_at);
  const endMs = Date.parse(sorted[sorted.length - 1].created_at);
  const startDateStr = new Date(startMs).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  const endDateStr = new Date(endMs).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  const dateRange = startDateStr === endDateStr ? startDateStr : `${startDateStr} – ${endDateStr}`;

  // 2. Median Calm index and variability (MAD)
  const scores = validRows.map(r => r.average);
  const medianScore = scores.length ? median(scores) : null;
  const madScore = scores.length ? mad(scores) : null;

  // 3. Repeat-scan consistency: consecutive scans within 30 minutes
  const thirtyMinMs = 30 * 60 * 1000;
  const repeatPairs = [];
  for (let i = 0; i < sorted.length - 1; i++) {
    const cur = sorted[i];
    const next = sorted[i + 1];
    if (Number.isFinite(cur.average) && Number.isFinite(next.average)) {
      const diffTime = Date.parse(next.created_at) - Date.parse(cur.created_at);
      if (diffTime >= 0 && diffTime <= thirtyMinMs) {
        repeatPairs.push(Math.abs(next.average - cur.average));
      }
    }
  }

  let repeatConsistency = null;
  if (repeatPairs.length >= 3) {
    repeatConsistency = median(repeatPairs);
  }

  // 4. Share of scans with Good quality
  const goodCount = rows.filter(r => r.quality === 'good' || r.qualityFlags && Object.values(r.qualityFlags).every(v => !v)).length;
  const goodQualityShare = rows.length > 0 ? (goodCount / rows.length) * 100 : 0;

  return {
    scansSaved,
    daysWithScans,
    dateRange,
    medianScore,
    madScore,
    repeatPairsCount: repeatPairs.length,
    repeatConsistency,
    goodQualityShare
  };
}
