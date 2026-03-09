from __future__ import annotations

import json

import higgs_agent.providers.hosted.openrouter as openrouter


class _FakeHTTPResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeHTTPResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_openrouter_http_transport_sends_higgsagent_identity_headers(monkeypatch) -> None:
    captured: dict[str, object] = {}
    response_payload = {"choices": [{"message": {"content": "ok"}}], "usage": {}}

    def fake_urlopen(request, timeout: float):
        captured["request"] = request
        captured["timeout"] = timeout
        return _FakeHTTPResponse(response_payload)

    monkeypatch.setattr(openrouter, "urlopen", fake_urlopen)

    transport = openrouter.OpenRouterHTTPTransport(api_key="test-key")
    payload = {"model": "openai/gpt-5.4", "messages": [{"role": "user", "content": "hello"}]}

    result = transport.complete(payload, timeout_ms=1500)

    assert result == response_payload
    assert captured["timeout"] == 1.5

    request = captured["request"]
    headers = {key.lower(): value for key, value in request.header_items()}
    assert request.full_url == "https://openrouter.ai/api/v1/chat/completions"
    assert json.loads(request.data.decode("utf-8")) == payload
    assert headers["authorization"] == "Bearer test-key"
    assert headers["content-type"] == "application/json"
    assert headers["http-referer"] == "https://github.com/muonium-ai/HiggsAgent"
    assert headers["x-openrouter-title"] == "HiggsAgent"
    assert headers["user-agent"] == "HiggsAgent"
