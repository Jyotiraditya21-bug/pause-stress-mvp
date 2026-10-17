import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import httpx
import main


class LocalBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(main, 'DB', Path(self.directory.name) / 'test.sqlite3')
        self.db_patch.start()
        main.request_times.clear()
        main.guidance_times.clear()
        self.lifespan = main.lifespan(main.app)
        await self.lifespan.__aenter__()

    async def asyncTearDown(self):
        await self.lifespan.__aexit__(None, None, None)
        self.db_patch.stop()
        self.directory.cleanup()

    def client(self, address='127.0.0.1'):
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app, client=(address, 1234)), base_url='http://127.0.0.1:8000')

    async def test_rejects_remote_clients_host_rebinding_and_cross_site_origin(self):
        async with self.client('192.0.2.1') as client:
            self.assertEqual((await client.get('/api/sessions')).status_code, 403)
        async with self.client() as client:
            for headers in [{'Host': 'attacker.example'}, {'Origin': 'https://attacker.example'}, {'Origin': 'null'}]:
                self.assertEqual((await client.get('/api/sessions', headers=headers)).status_code, 403)
            response = await client.get('/api/health', headers={'Origin': 'http://localhost:5173'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers['cache-control'], 'no-store')

    async def test_body_limits_validation_and_pagination(self):
        fields=dict(self_reported_stress=4,sleep_hours=7,workload='light',caffeine=False,recent_exercise=False,storage_consent=True)
        async with self.client() as client:
            self.assertEqual((await client.post('/api/sessions', content=b'x' * 65537)).status_code, 413)
            self.assertEqual((await client.post('/api/sessions', json=fields | {'storage_consent': False})).status_code, 422)
            for _ in range(3):
                self.assertEqual((await client.post('/api/sessions', json=fields)).status_code, 201)
            first = (await client.get('/api/sessions?limit=2')).json()['sessions']
            second = (await client.get('/api/sessions?limit=2&offset=2')).json()['sessions']
            self.assertEqual(len(first), 2)
            self.assertEqual(len(second), 1)
            self.assertNotIn(second[0]['id'], [r['id'] for r in first])
            self.assertEqual((await client.get('/api/sessions?limit=101')).status_code, 422)

    async def test_rate_limits_general_and_guidance_requests(self):
        async with self.client() as client:
            for _ in range(6):
                self.assertEqual((await client.post('/api/sessions/absent/guidance', json={'cloud_consent': False})).status_code, 404)
            self.assertEqual((await client.post('/api/sessions/absent/guidance', json={'cloud_consent': False})).status_code, 429)
            main.request_times.extend([main.time.monotonic()] * 120)
            response = await client.get('/api/health')
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.headers['retry-after'], '60')
