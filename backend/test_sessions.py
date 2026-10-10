import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pydantic import ValidationError
from fastapi import HTTPException
import main

class SessionsTests(unittest.TestCase):
    def test_lifecycle_and_validation_in_isolated_database(self):
        async def run():
            with tempfile.TemporaryDirectory() as directory, patch.object(main, 'DB', Path(directory)/'test.sqlite3'):
                async with main.lifespan(main.app):
                    fields=dict(self_reported_stress=4,sleep_hours=7,workload='light',caffeine=False,recent_exercise=False,storage_consent=True)
                    for change in [dict(self_reported_stress=11),dict(storage_consent=False),dict(sleep_hours=25)]:
                        with self.assertRaises(ValidationError):main.CheckIn(**(fields|change))
                    saved=main.create_session(main.CheckIn(**fields))
                    self.assertEqual(main.sessions()['sessions'][0]['id'],saved['id'])
                    guided=main.session_guidance(saved['id'],main.GuidanceRequest(cloud_consent=False))
                    self.assertEqual(guided['guidance']['source'],'local')
                    self.assertEqual(main.sessions()['sessions'][0]['guidance'],guided['guidance'])
                    main.guidance_lock.acquire()
                    try:
                        with self.assertRaises(HTTPException) as error:main.session_guidance(saved['id'],main.GuidanceRequest(cloud_consent=False))
                        self.assertEqual(error.exception.status_code,409)
                    finally:main.guidance_lock.release()
                    main.delete_session(saved['id'])
                    self.assertEqual(main.sessions()['sessions'],[])
                    with self.assertRaises(HTTPException):main.delete_session(saved['id'])
        asyncio.run(run())

if __name__=='__main__':unittest.main()
