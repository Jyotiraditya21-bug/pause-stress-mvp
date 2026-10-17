export const BASELINE_KEY = 'pause.baseline.v1';
export const ALGO_VERSION = 'quick-2.0';
export const BASELINE_MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000;

function validFeature(value) {
  return value && Number.isFinite(value.median) && Number.isFinite(value.mad) && value.mad >= 0;
}

export function readBaseline(storage = globalThis.localStorage, now = Date.now()) {
  try {
    const raw = storage?.getItem(BASELINE_KEY);
    if (!raw) return null;
    const value = JSON.parse(raw);
    const created = Date.parse(value?.createdAt);
    const keys = ['brow_furrow', 'lip_press', 'lip_corner', 'jaw_clench'];
    if (value?.algoVersion !== ALGO_VERSION || !Number.isFinite(created) || now - created > BASELINE_MAX_AGE_MS || now < created || !keys.every((key) => validFeature(value.features?.[key]))) {
      storage?.removeItem(BASELINE_KEY);
      return null;
    }
    return value;
  } catch {
    return null;
  }
}

export function saveBaseline(features, storage = globalThis.localStorage, now = Date.now()) {
  const value = { id: globalThis.crypto.randomUUID(), createdAt: new Date(now).toISOString(), algoVersion: ALGO_VERSION, features };
  try {
    storage?.setItem(BASELINE_KEY, JSON.stringify(value));
    return value;
  } catch {
    return null;
  }
}

export function resetBaseline(storage = globalThis.localStorage) {
  try {
    storage?.removeItem(BASELINE_KEY);
    return true;
  } catch {
    return false;
  }
}
