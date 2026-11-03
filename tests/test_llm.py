import json
import urllib.error

import pytest

from lecture_study.errors import TransientError
from lecture_study.llm import OllamaClient


class FakeResponse:
    def __init__(self, body):
        self._body = json.dumps(body).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def client(urlopen):
    return OllamaClient("http://127.0.0.1:11434/", "qwen2.5:7b", num_ctx=16384, timeout_seconds=600, urlopen=urlopen)


def test_complete_sends_non_streaming_chat_with_context_size():
    sent = []

    def urlopen(request, timeout):
        sent.append((request, timeout))
        return FakeResponse({"message": {"role": "assistant", "content": "## Tema"}})

    assert client(urlopen).complete("sistema", "testo") == "## Tema"
    request, timeout = sent[0]
    body = json.loads(request.data)
    assert request.full_url == "http://127.0.0.1:11434/api/chat"
    assert timeout == 600
    assert body["model"] == "qwen2.5:7b"
    assert body["stream"] is False
    assert body["options"]["num_ctx"] == 16384
    assert body["messages"] == [{"role": "system", "content": "sistema"}, {"role": "user", "content": "testo"}]


def test_unreachable_server_is_transient():
    def urlopen(request, timeout):
        raise urllib.error.URLError(ConnectionRefusedError())

    with pytest.raises(TransientError, match="unreachable"):
        client(urlopen).complete("s", "p")


def test_timeout_is_transient():
    def urlopen(request, timeout):
        raise TimeoutError("timed out")

    with pytest.raises(TransientError):
        client(urlopen).complete("s", "p")


def test_missing_model_is_transient():
    def urlopen(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 404, "not found", {}, None)

    with pytest.raises(TransientError, match="404"):
        client(urlopen).complete("s", "p")


def test_bad_request_is_not_retried():
    def urlopen(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 400, "bad request", {}, None)

    with pytest.raises(urllib.error.HTTPError):
        client(urlopen).complete("s", "p")


def test_release_unloads_model_and_ignores_unreachable_server():
    sent = []

    def urlopen(request, timeout):
        sent.append(request)
        return FakeResponse({"done": True})

    client(urlopen).release()
    assert sent[0].full_url == "http://127.0.0.1:11434/api/generate"
    assert json.loads(sent[0].data) == {"model": "qwen2.5:7b", "keep_alive": 0}

    def down(request, timeout):
        raise urllib.error.URLError(ConnectionRefusedError())

    client(down).release()
