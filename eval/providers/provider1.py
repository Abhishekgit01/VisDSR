"""OpenAI Responses API adapter."""
from __future__ import annotations

import base64
import os
import time

from eval.prompts import SYSTEM
from eval.providers.base import post_json


def call_model(prompt: str, image_bytes: bytes | None, settings: dict) -> dict:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is required")
    content = [{"type": "input_text", "text": prompt}]
    if image_bytes is not None:
        content.append({"type": "input_image", "image_url":
                        "data:image/png;base64," + base64.b64encode(image_bytes).decode(), "detail": "high"})
    payload = {"model": settings["id"], "instructions": SYSTEM,
               "input": [{"role": "user", "content": content}],
               "max_output_tokens": settings["max_output_tokens"], "store": False}
    if settings.get("temperature") is not None:
        payload["temperature"] = settings["temperature"]
    started = time.monotonic()
    response = post_json("https://api.openai.com/v1/responses", payload,
                         {"Authorization": f"Bearer {key}"})
    parts = [part.get("text", "") for item in response.get("output", [])
             for part in item.get("content", []) if part.get("type") == "output_text"]
    return {"raw_text": "".join(parts), "usage": response.get("usage", {}),
            "latency_s": time.monotonic() - started}
