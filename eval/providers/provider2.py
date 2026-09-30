"""Anthropic Messages API adapter."""
from __future__ import annotations

import base64
import os
import time

from eval.prompts import SYSTEM
from eval.providers.base import post_json


def call_model(prompt: str, image_bytes: bytes | None, settings: dict) -> dict:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is required")
    content = []
    if image_bytes is not None:
        source = {"type": "base64", "media_type": "image/png",
                  "data": base64.b64encode(image_bytes).decode()}
        content.append({"type": "image", "source": source})
    content.append({"type": "text", "text": prompt})
    payload = {"model": settings["id"], "system": SYSTEM,
               "messages": [{"role": "user", "content": content}],
               "max_tokens": settings["max_output_tokens"]}
    if settings.get("temperature") is not None:
        payload["temperature"] = settings["temperature"]
    started = time.monotonic()
    response = post_json("https://api.anthropic.com/v1/messages", payload,
                         {"x-api-key": key, "anthropic-version": "2023-06-01"})
    parts = [part.get("text", "") for part in response.get("content", []) if part.get("type") == "text"]
    return {"raw_text": "".join(parts), "usage": response.get("usage", {}),
            "latency_s": time.monotonic() - started}
