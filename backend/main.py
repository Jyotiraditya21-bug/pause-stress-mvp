from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
import os
import sqlite3
import json
from datetime import datetime, timezone
from uuid import uuid4
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Response
from guidance import generate_guidance
import threading
import ipaddress
import time
from collections import deque
from urllib.parse import urlsplit
from fastapi import Request
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')
DB = ROOT / 'sessions.sqlite3'

@contextmanager
def database():
    connection = sqlite3.connect(DB)
    try:
        with connection:
            yield connection
    finally:
        connection.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    with database() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
            self_reported_stress INTEGER, scan_quality TEXT,
            camera_metrics_json TEXT, guidance_json TEXT
        )''')
        columns = {row[1] for row in conn.execute('PRAGMA table_info(sessions)')}
        if 'context_json' not in columns:
            conn.execute('ALTER TABLE sessions ADD COLUMN context_json TEXT')
    yield

app = FastAPI(title='Stress Check MVP', version='0.1.0', lifespan=lifespan)

# The released product is static/on-device. This historical API is local-only;
# fail closed rather than accidentally expose unauthenticated personal records.
LOCAL_HOSTS = {'localhost', '127.0.0.1', '::1'}
request_times = deque()
guidance_times = deque()
request_lock = threading.Lock()

@app.middleware('http')
async def local_boundary(request: Request, call_next):
    try:
        local_client = ipaddress.ip_address(request.client.host).is_loopback
        local_host = urlsplit('http://' + request.headers.get('host', '')).hostname in LOCAL_HOSTS
        origin = request.headers.get('origin')
        local_origin = not origin or (urlsplit(origin).hostname in LOCAL_HOSTS and urlsplit(origin).scheme in {'http', 'https'})
    except (ValueError, AttributeError):
        local_client = local_host = local_origin = False
    if not (local_client and local_host and local_origin):
        return JSONResponse({'detail': 'This API accepts local-device requests only.'}, status_code=403)
    now = time.monotonic()
    with request_lock:
        for queue in (request_times, guidance_times):
            while queue and queue[0] <= now - 60:
                queue.popleft()
        guidance_call = request.method == 'POST' and request.url.path.endswith('/guidance')
        if len(request_times) >= 120 or (guidance_call and len(guidance_times) >= 6):
            return JSONResponse({'detail': 'Too many requests. Retry in a minute.'}, status_code=429, headers={'Retry-After': '60'})
        request_times.append(now)
        if guidance_call:
            guidance_times.append(now)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 65536:
            return JSONResponse({'detail': 'Request body exceeds 64 KiB.'}, status_code=413)
    request._body = bytes(body)
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

@app.get('/api/health')
def health():
    with database() as conn:
        conn.execute('SELECT 1')
    return {'status': 'ok', 'database': 'ready',
            'gemini_configured': bool(os.getenv('GEMINI_API_KEY', '').strip()),
            'phase': 4}

class CameraMetrics(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    quality: Literal['good', 'poor']
    usablePercent: int = Field(ge=0, le=100)
    frames: int = Field(ge=0, le=10000)
    durationSeconds: int = Field(ge=0, le=300)
    meanBlinkCoefficient: float | None = Field(default=None, ge=0, le=1)
    meanBrowCoefficient: float | None = Field(default=None, ge=0, le=1)
    meanMovement: float | None = Field(default=None, ge=0, le=2)

class CheckIn(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    self_reported_stress: int = Field(ge=0, le=10, strict=True)
    sleep_hours: float = Field(ge=0, le=24)
    workload: Literal['light', 'moderate', 'heavy']
    caffeine: bool
    recent_exercise: bool
    storage_consent: Literal[True]
    camera_metrics: CameraMetrics | None = None

def decode(row):
    data = dict(row)
    for field in ['camera_metrics', 'guidance', 'context']:
        raw = data.pop(field + '_json', None)
        data[field] = json.loads(raw) if raw else None
    return data

class GuidanceRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    cloud_consent: bool = Field(strict=True)

guidance_lock = threading.Lock()

@app.post('/api/sessions/{session_id}/guidance')
def session_guidance(session_id: str, body: GuidanceRequest):
    if not guidance_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail='Guidance is already being generated. Please retry shortly.')
    try:
        with database() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM sessions WHERE id=?', (session_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail='Session not found')
        guidance = generate_guidance(decode(row), body.cloud_consent)
        with database() as conn:
            conn.row_factory = sqlite3.Row
            updated = conn.execute('UPDATE sessions SET guidance_json=? WHERE id=?', (json.dumps(guidance), session_id))
            if not updated.rowcount:
                raise HTTPException(status_code=404, detail='Session was deleted')
            row = conn.execute('SELECT * FROM sessions WHERE id=?', (session_id,)).fetchone()
        return decode(row)
    finally:
        guidance_lock.release()

@app.post('/api/sessions', status_code=201)
def create_session(body: CheckIn):
    session_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    camera = body.camera_metrics.model_dump() if body.camera_metrics else None
    context = body.model_dump(exclude={'self_reported_stress', 'camera_metrics'})
    with database() as conn:
        conn.row_factory = sqlite3.Row
        conn.execute('INSERT INTO sessions (id,created_at,self_reported_stress,scan_quality,camera_metrics_json,context_json) VALUES (?,?,?,?,?,?)',
                     (session_id, created_at, body.self_reported_stress, camera['quality'] if camera else 'unavailable', json.dumps(camera) if camera else None, json.dumps(context)))
        row = conn.execute('SELECT * FROM sessions WHERE id=?', (session_id,)).fetchone()
    return decode(row)

@app.delete('/api/sessions/{session_id}', status_code=204)
def delete_session(session_id: str):
    with database() as conn:
        result = conn.execute('DELETE FROM sessions WHERE id=?', (session_id,))
        if not result.rowcount:
            raise HTTPException(status_code=404, detail='Session not found')
    return Response(status_code=204)

@app.get('/api/sessions')
def sessions(limit: int = 100, offset: int = 0):
    if not 1 <= limit <= 100 or offset < 0:
        raise HTTPException(status_code=422, detail='Use limit 1–100 and offset >= 0.')
    with database() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute('SELECT * FROM sessions ORDER BY created_at DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    return {'sessions': [decode(row) for row in rows]}

@app.get('/api/schema')
def schema():
    return {'screens': ['overview', 'check-in', 'results', 'history'],
            'result_fields': {
                'self_reported_stress': '0–10 rating; user supplied',
                'scan_quality': 'good | poor | unavailable',
                'camera_metrics': 'experimental facial features; not a stress score',
                'guidance': 'summary and suggested actions; phase 4',
                'created_at': 'UTC ISO timestamp'},
            'ai_stress_prediction': 'Not enabled; requires a validated trained model'}
