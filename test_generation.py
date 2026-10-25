"""Generation contract checks; never call or charge the image API."""
import base64
import json
import threading
import unittest
import urllib.request
from io import BytesIO
from unittest.mock import patch

import folio_press as app
from PIL import Image


class GenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        image = Image.new("RGB", (3, 1))
        image.putdata([(0, 0, 0), (120, 120, 120), (255, 255, 255)])
        stream = BytesIO()
        image.save(stream, format="PNG")
        cls.original = base64.b64encode(stream.getvalue()).decode()
        cls.server = app.Press(("127.0.0.1", 0), app.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def compose(self, **overrides):
        data = dict(key="test-only-key", subject="Two cats in a cozy kitchen", level="medium")
        data.update(overrides)
        request = urllib.request.Request(
            "http://127.0.0.1:%d/compose" % self.server.server_port,
            json.dumps(data).encode(), {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as response:
            return response.code, json.load(response)

    def test_audiences_keep_models_and_preserve_original_linework(self):
        for level, model in [("easy", "gpt-image-2.5-flare"),
                             ("medium", "gpt-image-2.5-flare"),
                             ("detailed", "gpt-image-2.5-sunburst")]:
            with self.subTest(level=level), patch.object(app, "generate_image", return_value=(self.original, None)) as generate:
                status, result = self.compose(level=level)
                self.assertEqual(status, 200)
                self.assertEqual(result["image"], self.original)
                self.assertNotIn("original_image", result)
                self.assertEqual(generate.call_args.args[2], model)
                self.assertEqual(result["generation"]["prompt"], generate.call_args.args[1])
                self.assertEqual(result["generation"]["width"], 3)
                self.assertNotIn("test-only-key", json.dumps(result))

    def test_style_reference_precedes_character_identity_references(self):
        char_ref = base64.b64encode(b"character-ref").decode()
        with patch.object(app, "generate_with_references", return_value=(self.original, None)) as generate:
            status, result = self.compose(style_reference=self.original, references=[char_ref],
                                         characters=[{"name": "Milo", "description": "tabby"}])
            self.assertEqual(status, 200)
            self.assertEqual(generate.call_args.args[2], [base64.b64decode(self.original), b"character-ref"])
            self.assertIn("FIRST input image", result["generation"]["prompt"])
            self.assertIn("Milo: tabby", result["generation"]["prompt"])
            self.assertEqual(result["generation"]["reference_count"], 2)

    def test_cleanup_retains_the_exact_original(self):
        with patch.object(app, "generate_image", return_value=(self.original, None)):
            status, result = self.compose(cleanup=True)
        self.assertEqual(status, 200)
        self.assertEqual(result["original_image"], self.original)
        self.assertNotEqual(result["image"], self.original)
        pixels = Image.open(BytesIO(base64.b64decode(result["image"]))).convert("L")
        self.assertEqual([pixels.getpixel((x, 0)) for x in range(3)], [0, 255, 255])

    def test_bad_audience_and_reference_fail_before_generation(self):
        with patch.object(app, "generate_image") as generate, patch.object(app, "generate_with_references") as refs:
            for overrides in [{"level": "unknown"}, {"style_reference": "not-base64!"}]:
                self.assertEqual(self.compose(**overrides)[0], 400)
            generate.assert_not_called()
            refs.assert_not_called()

    def test_provider_error_is_returned_without_a_false_success(self):
        with patch.object(app, "generate_image", return_value=(None, "provider unavailable")):
            status, result = self.compose()
        self.assertEqual(status, 400)
        self.assertEqual(result, {"error": "provider unavailable"})


if __name__ == "__main__":
    unittest.main()
