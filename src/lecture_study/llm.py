from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Callable, Protocol

from lecture_study.errors import TransientError


class LanguageModel(Protocol):
    def complete(self, system: str, prompt: str) -> str: ...

    def release(self) -> None: ...


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        num_ctx: int,
        timeout_seconds: int,
        urlopen: Callable[..., Any] = urllib.request.urlopen,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self.model = model
        self._num_ctx = num_ctx
        self._timeout = timeout_seconds
        self._urlopen = urlopen

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            self._base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._urlopen(request, timeout=self._timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404 or exc.code >= 500:
                raise TransientError(f"Ollama ha risposto {exc.code} per il modello {self.model}") from exc
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise TransientError(f"Ollama non raggiungibile: {exc}") from exc

    def complete(self, system: str, prompt: str) -> str:
        data = self._post(
            "/api/chat",
            {
                "model": self.model,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                "stream": False,
                "options": {"num_ctx": self._num_ctx, "temperature": 0.2},
            },
        )
        return data.get("message", {}).get("content", "")

    def release(self) -> None:
        try:
            self._post("/api/generate", {"model": self.model, "keep_alive": 0})
        except TransientError:
            pass
