"""Network-free adapter and retry contract tests."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from eval.prompts import SYSTEM
from eval.providers.base import TransientProviderError
from eval.providers import provider1, provider2
from eval.run import call_with_retries


class ProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = {"id": "test-vision-model", "temperature": 0,
                         "max_output_tokens": 1024}

    def test_openai_payload(self) -> None:
        response = {"output": [{"content": [{"type": "output_text", "text": "{}"}]}],
                    "usage": {"input_tokens": 1}}
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-only"}), \
                patch.object(provider1, "post_json", return_value=response) as post:
            result = provider1.call_model("prompt", b"png", self.settings)
        self.assertEqual(result["raw_text"], "{}")
        payload = post.call_args.args[1]
        self.assertEqual(payload["instructions"], SYSTEM)
        self.assertFalse(payload["store"])
        self.assertTrue(payload["input"][0]["content"][1]["image_url"].startswith("data:image/png;base64,"))

    def test_anthropic_payload(self) -> None:
        response = {"content": [{"type": "text", "text": "{}"}], "usage": {}}
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-only"}), \
                patch.object(provider2, "post_json", return_value=response) as post:
            result = provider2.call_model("prompt", b"png", self.settings)
        self.assertEqual(result["raw_text"], "{}")
        payload = post.call_args.args[1]
        self.assertEqual(payload["system"], SYSTEM)
        self.assertEqual(payload["messages"][0]["content"][0]["source"]["media_type"], "image/png")

    def test_only_transient_failures_retry(self) -> None:
        effects = [TransientProviderError("rate limit"), {"raw_text": "{}"}]
        with patch.object(provider1, "call_model", side_effect=effects) as call, \
                patch("eval.run.time.sleep") as sleep:
            result = call_with_retries("openai", "prompt", None, self.settings)
        self.assertEqual(result["raw_text"], "{}")
        self.assertEqual(call.call_count, 2)
        sleep.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()
