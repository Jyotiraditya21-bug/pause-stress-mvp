from contextlib import asynccontextmanager
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

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')
DB = ROOT / 'sessions.sqlite3'

@asynccontextmanager
async def lifespan(app: FastAPI):
    with sqlite3.connect(DB) as conn:
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

@app.get('/api/health')
def health():
    with sqlite3.connect(DB) as conn:
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
        with sqlite3.connect(DB) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute('SELECT * FROM sessions WHERE id=?', (session_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail='Session not found')
        guidance = generate_guidance(decode(row), body.cloud_consent)
        with sqlite3.connect(DB) as conn:
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
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute('INSERT INTO sessions (id,created_at,self_reported_stress,scan_quality,camera_metrics_json,context_json) VALUES (?,?,?,?,?,?)',
                     (session_id, created_at, body.self_reported_stress, camera['quality'] if camera else 'unavailable', json.dumps(camera) if camera else None, json.dumps(context)))
        row = conn.execute('SELECT * FROM sessions WHERE id=?', (session_id,)).fetchone()
    return decode(row)

@app.delete('/api/sessions/{session_id}', status_code=204)
def delete_session(session_id: str):
    with sqlite3.connect(DB) as conn:
        result = conn.execute('DELETE FROM sessions WHERE id=?', (session_id,))
        if not result.rowcount:
            raise HTTPException(status_code=404, detail='Session not found')
    return Response(status_code=204)

@app.get('/api/sessions')
def sessions():
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute('SELECT * FROM sessions ORDER BY created_at DESC').fetchall()
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
