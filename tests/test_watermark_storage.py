import io
from PIL import Image
from app.watermark import add_visible_watermark, resize_image
from app import storage as storage_mod
import importlib
from app import config
import importlib
from app import config

def test_watermark_returns_png_bytes(tiny_png_bytes):
    out = add_visible_watermark(tiny_png_bytes, doc_id="abc123")
    assert isinstance(out, bytes)
    img = Image.open(io.BytesIO(out))
    assert img.format == "PNG"


def test_watermark_preserves_dimensions(tiny_png_bytes):
    before = Image.open(io.BytesIO(tiny_png_bytes)).size
    out = add_visible_watermark(tiny_png_bytes, doc_id="abc123")
    after = Image.open(io.BytesIO(out)).size
    assert before == after


def test_watermark_changes_pixels(big_png_bytes):
    out = add_visible_watermark(big_png_bytes, doc_id="stamp-me")
    assert out != big_png_bytes


def test_resize_shrinks_large_image(big_png_bytes):
    out = resize_image(big_png_bytes, max_dim=1024)
    w, h = Image.open(io.BytesIO(out)).size
    assert max(w, h) <= 1024


def test_resize_preserves_aspect_ratio(big_png_bytes):
    out = resize_image(big_png_bytes, max_dim=1024)
    w, h = Image.open(io.BytesIO(out)).size
    assert abs((w / h) - (3000 / 2000)) < 0.01


def test_resize_leaves_small_image(tiny_png_bytes):
    out = resize_image(tiny_png_bytes, max_dim=1024)
    w, h = Image.open(io.BytesIO(out)).size
    assert (w, h) == (4, 4)


def test_local_storage_round_trip(tmp_path):
    store = storage_mod.LocalStorage(str(tmp_path))
    data = b"hello-bytes"
    path = store.save("doc1", "watermarked.png", data)
    assert store.exists(path)
    assert store.load(path) == data


def test_local_storage_missing_file(tmp_path):
    store = storage_mod.LocalStorage(str(tmp_path))
    assert store.exists(str(tmp_path / "nope" / "missing.png")) is False


def test_local_storage_writes_under_doc_id(tmp_path):
    store = storage_mod.LocalStorage(str(tmp_path))
    path = store.save("docXYZ", "watermarked.png", b"x")
    assert "docXYZ" in path


def test_factory_returns_local_by_default(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    importlib.reload(config)
    importlib.reload(storage_mod)
    store = storage_mod.get_storage()
    assert store.__class__.__name__ == "LocalStorage"


def test_factory_returns_s3_when_set(monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("S3_BUCKET", "test-bucket")
    monkeypatch.setenv("AWS_REGION", "ap-south-1")
    importlib.reload(config)
    importlib.reload(storage_mod)
    store = storage_mod.get_storage()
    assert store.__class__.__name__ == "S3Storage"
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    importlib.reload(config)
    importlib.reload(storage_mod)
