import io
import json
import unittest
from unittest.mock import patch
import urllib.error
from guidance import generate_guidance, request_gemini

SESSION = {'self_reported_stress': 6, 'id': 'private-id',
           'camera_metrics': {'private': 'facial-data'},
           'context': {'sleep_hours': 7, 'workload': 'heavy', 'caffeine': False, 'recent_exercise': True}}

class GuidanceTests(unittest.TestCase):
    def test_no_consent_never_calls_provider(self):
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-only'}):
            def fail(_):
                self.fail('Provider called without consent')
            result = generate_guidance(SESSION, False, fail)
            self.assertEqual(result['source'], 'local')

    def test_missing_key_falls_back(self):
        with patch.dict('os.environ', {'GEMINI_API_KEY': ''}):
            self.assertEqual(generate_guidance(SESSION, True)['status'], 'missing_key')

    def test_request_excludes_sensitive_camera_and_identity(self):
        def transport(request, timeout):
            self.assertEqual(timeout, 20)
            body = json.loads(request.data)
            inputs = json.loads(body['contents'][0]['parts'][0]['text'])
            self.assertEqual(set(inputs), {'self_reported_stress', 'sleep_hours', 'workload', 'caffeine', 'recent_exercise'})
            return io.BytesIO(json.dumps({'candidates': [{'content': {'parts': [{'text': json.dumps({'focus': 'workload', 'actions': ['prioritize', 'connect']})}]}}]}).encode())
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-only'}), patch('urllib.request.urlopen', transport):
            result = generate_guidance(SESSION, True)
            self.assertEqual(result['source'], 'gemini')
            self.assertIn('6/10', result['summary'])

    def test_malformed_output_and_provider_errors_fall_back(self):
        for text in ['not json', '{"focus":"diagnosis","actions":["pause","reflect"]}', '{"focus":"pause","actions":["pause","pause"]}']:
            raw = json.dumps({'candidates':[{'content':{'parts':[{'text':text}]}}]}).encode()
            with patch.dict('os.environ', {'GEMINI_API_KEY':'test-only'}), patch('urllib.request.urlopen', return_value=io.BytesIO(raw)):
                self.assertEqual(generate_guidance(SESSION, True)['source'], 'local')
        for error in [TimeoutError(), urllib.error.HTTPError('url', 429, 'secret must not leak', {}, None)]:
            with patch.dict('os.environ', {'GEMINI_API_KEY':'test-only'}), patch('urllib.request.urlopen', side_effect=error):
                result = generate_guidance(SESSION, True)
                self.assertEqual(result['source'], 'local')
                self.assertNotIn('secret', json.dumps(result))

if __name__ == '__main__':
    unittest.main()
