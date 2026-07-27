import importlib
import pytest


def reload_moderation():
    from app import config, moderation
    importlib.reload(config)
    importlib.reload(moderation)
    return moderation


def test_gate_off_allows_without_api(monkeypatch, tiny_png_bytes):
    monkeypatch.setenv("MODERATION_SET", "false")
    moderation = reload_moderation()

    monkeypatch.setattr(moderation, "_moderation_client",
                        lambda: (_ for _ in ()).throw(AssertionError("client built")))

    verdict = moderation.moderate_image(tiny_png_bytes, image_type="image/png")
    assert verdict.allowed is True


def test_gate_on_without_key_raises(monkeypatch, tiny_png_bytes):
    monkeypatch.setenv("MODERATION_SET", "true")
    monkeypatch.setenv("MODERATION_API_KEY", "")
    moderation = reload_moderation()

    with pytest.raises(moderation.ModerationConfigError):
        moderation.moderate_image(tiny_png_bytes, image_type="image/png")


def test_gate_on_clean_image_allowed(monkeypatch, tiny_png_bytes):
    monkeypatch.setenv("MODERATION_SET", "true")
    monkeypatch.setenv("MODERATION_API_KEY", "sk-test")
    moderation = reload_moderation()

    fake = _fake_client(flagged=False, scores={"violence": 0.01})
    monkeypatch.setattr(moderation, "_moderation_client", lambda: fake)

    verdict = moderation.moderate_image(tiny_png_bytes, image_type="image/png")
    assert verdict.allowed is True


def test_gate_on_flagged_image_blocked(monkeypatch, tiny_png_bytes):
    monkeypatch.setenv("MODERATION_SET", "true")
    monkeypatch.setenv("MODERATION_API_KEY", "sk-test")
    moderation = reload_moderation()

    fake = _fake_client(flagged=True, scores={"violence": 0.99})
    monkeypatch.setattr(moderation, "_moderation_client", lambda: fake)

    verdict = moderation.moderate_image(tiny_png_bytes, image_type="image/png")
    assert verdict.allowed is False
    assert verdict.blocked_reason


def test_gate_on_over_threshold_blocks(monkeypatch, tiny_png_bytes):
    monkeypatch.setenv("MODERATION_SET", "true")
    monkeypatch.setenv("MODERATION_API_KEY", "sk-test")
    monkeypatch.setenv("MODERATION_THRESHOLD", "0.5")
    moderation = reload_moderation()

    fake = _fake_client(flagged=False, scores={"nsfw": 0.92})
    monkeypatch.setattr(moderation, "_moderation_client", lambda: fake)

    verdict = moderation.moderate_image(tiny_png_bytes, image_type="image/png")
    assert verdict.allowed is False


def _fake_client(flagged, scores):
    class _Result:
        def __init__(self):
            self.flagged = flagged
            self.category_scores = scores

    class _Resp:
        def __init__(self):
            self.results = [_Result()]

    class _Moderations:
        def create(self, **kwargs):
            return _Resp()

    class _Client:
        def __init__(self):
            self.moderations = _Moderations()

    return _Client()
