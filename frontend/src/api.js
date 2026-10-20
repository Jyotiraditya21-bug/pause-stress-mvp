export const browserOnly = import.meta.env.VITE_STORAGE_MODE === 'browser';
const KEY = 'pause-checkins-v1';

function read() {
  const rows = JSON.parse(localStorage.getItem(KEY) || '[]');
  if (!Array.isArray(rows)) throw new Error('Saved browser data is invalid.');
  return rows;
}

function response(data, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  };
}

export async function api(path, options = {}) {
  if (!browserOnly) {
    return fetch((import.meta.env.VITE_API_BASE_URL || '') + path, options);
  }

  try {
    if (path === '/api/health') {
      return response({ status: 'ok', database: 'browser', gemini_configured: false });
    }

    if (path === '/api/sessions' && (!options.method || options.method === 'GET')) {
      return response({ sessions: read() });
    }

    const body = options.body ? JSON.parse(options.body) : {};

    if (path === '/api/sessions' && options.method === 'POST') {
      if (
        !body.storage_consent ||
        !Number.isInteger(body.self_reported_stress) ||
        body.self_reported_stress < 0 ||
        body.self_reported_stress > 10 ||
        !Number.isFinite(body.sleep_hours) ||
        body.sleep_hours < 0 ||
        body.sleep_hours > 24
      ) {
        return response({}, 422);
      }

      const { camera_metrics, self_reported_stress, ...context } = body;
      const saved = {
        id: crypto.randomUUID(),
        created_at: new Date().toISOString(),
        self_reported_stress,
        context,
        camera_metrics: camera_metrics || null,
        scan_quality: camera_metrics?.quality || 'unavailable',
        guidance: null,
      };

      localStorage.setItem(KEY, JSON.stringify([saved, ...read()]));
      return response(saved, 201);
    }

    const match = path.match(/^\/api\/sessions\/([^/]+)(\/guidance)?$/);
    if (match) {
      const rows = read();
      const row = rows.find((s) => s.id === match[1]);
      if (!row) return response({}, 404);

      if (options.method === 'DELETE') {
        localStorage.setItem(KEY, JSON.stringify(rows.filter((s) => s.id !== row.id)));
        return response(null, 204);
      }

      if (options.method === 'POST' && match[2]) {
        if (body.cloud_consent) return response({}, 503);
        row.guidance = {
          source: 'local',
          status: 'local_requested',
          model: null,
          generated_at: new Date().toISOString(),
          summary: `You reported ${row.self_reported_stress}/10 stress. Take a moment to reflect on what would help today.`,
          actions: [
            'Take a brief break from your current task.',
            'Choose one manageable next step or check in with someone you trust.',
          ],
          limitations:
            'Based on your self-report, not a clinical assessment. Camera signals do not establish stress.',
        };
        localStorage.setItem(KEY, JSON.stringify(rows));
        return response(row);
      }
    }

    return response({}, 404);
  } catch {
    throw new Error('Browser storage is unavailable or full. Check your browser settings.');
  }
}
