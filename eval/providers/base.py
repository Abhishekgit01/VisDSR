"""Provider-independent result and transient failure contract."""
from __future__ import annotations

import json
import urllib.error
import urllib.request


class TransientProviderError(RuntimeError):
    pass


def post_json(url: str, payload: dict, headers: dict[str, str]) -> dict:
    request = urllib.request.Request(url, json.dumps(payload).encode(),
                                     {"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read(500).decode(errors="replace")
        if exc.code in (408, 409, 429) or 500 <= exc.code < 600:
            raise TransientProviderError(f"HTTP {exc.code}: {body}") from exc
        raise RuntimeError(f"provider HTTP {exc.code}: {body}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise TransientProviderError(str(exc)) from exc
