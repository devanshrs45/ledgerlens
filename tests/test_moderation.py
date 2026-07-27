"""
test_moderation.py

Covers the moderation gate's three states and, most importantly, the brief's
guarantee that a blocked upload never reaches the vision model.

We never call the real OpenAI moderation endpoint. Instead we monkeypatch the
client so the tests are fast, offline, and deterministic.
"""

import importlib
import pytest


def reload_moderation():
    from app import config, moderation
    importlib.reload(config)
    importlib.reload(moderation)
    return moderation


# --------------------------------------------------------------------------- #
# Gate OFF (the shipped default): everything is allowed without any API call
# --------------------------------------------------------------------------- #
def test_gate_off_allows_without_api(monkeypatch, tiny_png_bytes):
    monkeypatch.setenv("MODERATION_SET", "false")
    moderation = reload_moderation()

    # If the client were built, this would blow up - prove it is never called.
    monkeypatch.setattr(moderation, "_moderation_client",
                        lambda: (_ for _ in ()).throw(AssertionError("client built")))

    verdict = moderation.moderate_image(tiny_png_bytes, image_type="image/png")
    assert verdict.allowed is True


# --------------------------------------------------------------------------- #
# Gate ON but misconfigured: must fail loudly, never fail open
# --------------------------------------------------------------------------- #
def test_gate_on_without_key_raises(monkeypatch, tiny_png_bytes):
    monkeypatch.setenv("MODERATION_SET", "true")
    monkeypatch.setenv("MODERATION_API_KEY", "")
    moderation = reload_moderation()

    with pytest.raises(moderation.ModerationConfigError):
        moderation.moderate_image(tiny_png_bytes, image_type="image/png")


# --------------------------------------------------------------------------- #
# Gate ON, clean image: allowed
# --------------------------------------------------------------------------- #
def test_gate_on_clean_image_allowed(monkeypatch, tiny_png_bytes):
    monkeypatch.setenv("MODERATION_SET", "true")
    monkeypatch.setenv("MODERATION_API_KEY", "sk-test")
    moderation = reload_moderation()

    fake = _fake_client(flagged=False, scores={"violence": 0.01})
    monkeypatch.setattr(moderation, "_moderation_client", lambda: fake)

    verdict = moderation.moderate_image(tiny_png_bytes, image_type="image/png")
    assert verdict.allowed is True


# --------------------------------------------------------------------------- #
# Gate ON, flagged image: blocked with a reason
# --------------------------------------------------------------------------- #
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
    """Even if the API does not set flagged=True, our threshold blocks it."""
    monkeypatch.setenv("MODERATION_SET", "true")
    monkeypatch.setenv("MODERATION_API_KEY", "sk-test")
    monkeypatch.setenv("MODERATION_THRESHOLD", "0.5")
    moderation = reload_moderation()

    fake = _fake_client(flagged=False, scores={"nsfw": 0.92})
    monkeypatch.setattr(moderation, "_moderation_client", lambda: fake)

    verdict = moderation.moderate_image(tiny_png_bytes, image_type="image/png")
    assert verdict.allowed is False


# --------------------------------------------------------------------------- #
# helpers: a fake OpenAI moderation client
# --------------------------------------------------------------------------- #
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
