"""Tests du repli DeepSeek dans `agents/mistral_client.py` — pur, sans DB,
sans réseau : `_complete_with_messages` (l'appel Mistral réel) et l'appel
HTTP DeepSeek (`httpx.post`) sont tous deux monkeypatchés, donc ces tests
n'exigent ni clé API ni connectivité, comme `tests/test_agents.py`."""
import agents.mistral_client as mistral_client


def _fail_mistral(*args, **kwargs):
    raise mistral_client.MistralUnavailableError("Échec de l'appel Mistral après 3 tentatives : 429 rate limit")


class _FakeDeepSeekResponse:
    def __init__(self, content):
        self._content = content

    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


def test_complete_falls_back_to_deepseek_when_mistral_unavailable(monkeypatch):
    monkeypatch.setattr(mistral_client, "_complete_with_messages", _fail_mistral)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")

    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["model"] = json["model"]
        captured["messages"] = json["messages"]
        return _FakeDeepSeekResponse("Réponse DeepSeek de repli.")

    monkeypatch.setattr(mistral_client.httpx, "post", fake_post)

    result = mistral_client.complete("system prompt", "question", model=mistral_client.MODEL_SMALL)

    assert result == "Réponse DeepSeek de repli."
    assert captured["url"] == mistral_client.DEEPSEEK_API_URL
    assert captured["model"] == "deepseek-chat"
    assert captured["messages"][1]["content"] == "question"


def test_complete_uses_reasoner_model_for_model_large(monkeypatch):
    monkeypatch.setattr(mistral_client, "_complete_with_messages", _fail_mistral)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")

    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["model"] = json["model"]
        return _FakeDeepSeekResponse("ok")

    monkeypatch.setattr(mistral_client.httpx, "post", fake_post)

    mistral_client.complete("system", "question", model=mistral_client.MODEL_LARGE)

    assert captured["model"] == "deepseek-reasoner"


def test_complete_reraises_original_mistral_error_when_no_deepseek_key(monkeypatch):
    monkeypatch.setattr(mistral_client, "_complete_with_messages", _fail_mistral)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("DeepSeek ne doit pas être appelé sans DEEPSEEK_API_KEY")

    monkeypatch.setattr(mistral_client.httpx, "post", fail_if_called)

    try:
        mistral_client.complete("system", "question")
        assert False, "devait lever MistralUnavailableError"
    except mistral_client.MistralUnavailableError as err:
        assert "429 rate limit" in str(err)


def test_complete_reraises_mistral_error_when_deepseek_also_fails(monkeypatch):
    monkeypatch.setattr(mistral_client, "_complete_with_messages", _fail_mistral)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")

    def fake_post(*args, **kwargs):
        raise RuntimeError("DeepSeek injoignable")

    monkeypatch.setattr(mistral_client.httpx, "post", fake_post)

    try:
        mistral_client.complete("system", "question")
        assert False, "devait lever MistralUnavailableError"
    except mistral_client.MistralUnavailableError as err:
        assert "429 rate limit" in str(err)
        assert "DeepSeek injoignable" in str(err)


def test_complete_vision_reshapes_image_url_for_deepseek(monkeypatch):
    monkeypatch.setattr(mistral_client, "_complete_with_messages", _fail_mistral)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")

    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["model"] = json["model"]
        captured["content"] = json["messages"][1]["content"]
        return _FakeDeepSeekResponse("description du graphique")

    monkeypatch.setattr(mistral_client.httpx, "post", fake_post)

    result = mistral_client.complete_vision(
        "system", "décris ce graphique", ["data:image/png;base64,AAAA"]
    )

    assert result == "description du graphique"
    assert captured["model"] == mistral_client.DEEPSEEK_VISION_MODEL
    image_part = captured["content"][1]
    assert image_part["image_url"] == {"url": "data:image/png;base64,AAAA"}


def test_complete_with_allow_fallback_false_reraises_immediately_without_calling_deepseek(monkeypatch):
    monkeypatch.setattr(mistral_client, "_complete_with_messages", _fail_mistral)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("DeepSeek ne doit pas être appelé quand allow_fallback=False")

    monkeypatch.setattr(mistral_client.httpx, "post", fail_if_called)

    try:
        mistral_client.complete("system", "question", allow_fallback=False)
        assert False, "devait lever MistralUnavailableError"
    except mistral_client.MistralUnavailableError as err:
        assert "429 rate limit" in str(err)


def test_complete_does_not_call_deepseek_when_mistral_succeeds(monkeypatch):
    monkeypatch.setattr(mistral_client, "_complete_with_messages", lambda *a, **k: "réponse Mistral normale")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("DeepSeek ne doit pas être appelé quand Mistral réussit")

    monkeypatch.setattr(mistral_client.httpx, "post", fail_if_called)

    result = mistral_client.complete("system", "question")

    assert result == "réponse Mistral normale"
