"""API contract tests; model output is injected, no crop model accuracy is tested."""
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from fastapi.testclient import TestClient
from PIL import Image
import main


class Array:
    def __init__(self, value): self.value = value
    def cpu(self): return self
    def tolist(self): return self.value


def photo():
    f = io.BytesIO()
    Image.new('RGB', (100, 80), 'green').save(f, format='PNG')
    return f.getvalue()


class ContractTests(unittest.TestCase):
    def setUp(self):
        main.model = None
        main.loaded_path = None
        self.client = TestClient(main.app)
        self.env = patch.dict(os.environ, {'WALLACEA_MODEL_PATH': '', 'WALLACEA_LABEL_MAP_JSON': '{"plant":"plant"}', 'WALLACEA_CONFIDENCE': '0.35'})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        main.model = None
        main.loaded_path = None

    def test_health_does_not_claim_model_ready(self):
        r = self.client.get('/health')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()['model_configured'])
        self.assertFalse(r.json()['flight_control'])

    def test_valid_image_without_weights_returns_503(self):
        r = self.client.post('/analyze', files={'file': ('field.png', photo(), 'image/png')})
        self.assertEqual(r.status_code, 503)
        self.assertIn('Model tanaman belum tersedia', r.json()['detail'])

    def test_corrupt_image_returns_400(self):
        r = self.client.post('/analyze', files={'file': ('field.png', b'not-an-image', 'image/png')})
        self.assertEqual(r.status_code, 400)

    def test_unsupported_type_returns_415(self):
        r = self.client.post('/analyze', files={'file': ('field.svg', b'<svg/>', 'image/svg+xml')})
        self.assertEqual(r.status_code, 415)

    def test_cors_only_allows_configured_origin(self):
        r = self.client.options('/analyze', headers={'Origin': 'http://localhost:8080', 'Access-Control-Request-Method': 'POST'})
        self.assertEqual(r.headers.get('access-control-allow-origin'), 'http://localhost:8080')
        r = self.client.options('/analyze', headers={'Origin': 'https://unlisted.example', 'Access-Control-Request-Method': 'POST'})
        self.assertNotIn('access-control-allow-origin', r.headers)

    def test_injected_model_returns_normalized_reviewable_boxes(self):
        result = SimpleNamespace(names={0: 'plant'}, boxes=SimpleNamespace(xyxy=Array([[10, 16, 30, 40]]), conf=Array([0.87]), cls=Array([0])))
        with tempfile.TemporaryDirectory() as directory:
            weights = Path(directory) / 'custom.pt'
            weights.touch()
            os.environ['WALLACEA_MODEL_PATH'] = str(weights)
            main.model = SimpleNamespace(names={0: 'plant'}, predict=lambda *a, **k: [result])
            main.loaded_path = str(weights.resolve())
            r = self.client.post('/analyze', files={'file': ('field.png', photo(), 'image/png')})
            self.assertEqual(r.status_code, 200)
            payload = r.json()
            self.assertEqual(payload['image_width'], 100)
            self.assertTrue(payload['requires_review'])
            self.assertFalse(payload['georeferenced'])
            self.assertEqual(payload['detections'][0]['bbox'], [0.1, 0.2, 0.19999999999999998, 0.3])


if __name__ == '__main__':
    unittest.main(verbosity=2)
