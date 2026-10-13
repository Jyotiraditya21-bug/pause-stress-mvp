export const SCAN_STATES = Object.freeze(['idle', 'permission', 'loading', 'positioning', 'countdown', 'analyzing', 'result', 'failed']);
export const REQUIRED_GOOD_SECONDS = 10;
export const POSITIONING_SECONDS = 1;
export const BAD_PAUSE_SECONDS = .6;
export const HARD_CAP_SECONDS = 25;

export function createScanState(now = 0) {
  return { state: 'positioning', wallStartedAt: now, lastAt: now, goodSince: null, badSince: null, goodElapsed: 0, paused: false };
}

export function advanceScanState(current, now, good) {
  if (!Number.isFinite(now) || now < current.lastAt || ['analyzing', 'result', 'failed'].includes(current.state)) return current;
  const next = { ...current };
  const dt = Math.max(0, now - current.lastAt);
  next.lastAt = now;
  if (now - current.wallStartedAt >= HARD_CAP_SECONDS) return { ...next, state: 'analyzing', capped: true };

  if (next.state === 'positioning') {
    if (good) {
      next.goodSince ??= now;
      if (now - next.goodSince >= POSITIONING_SECONDS) {
        next.state = 'countdown';
        next.goodElapsed = 0;
        next.badSince = null;
      }
    } else {
      next.goodSince = null;
    }
    return next;
  }

  if (next.state === 'countdown') {
    if (good) {
      next.badSince = null;
      next.paused = false;
      next.goodElapsed = Math.min(REQUIRED_GOOD_SECONDS, next.goodElapsed + dt);
      if (next.goodElapsed >= REQUIRED_GOOD_SECONDS) next.state = 'analyzing';
    } else {
      next.badSince ??= now;
      if (now - next.badSince > BAD_PAUSE_SECONDS) next.paused = true;
    }
  }
  return next;
}
