import io
import json
import time
import zipfile

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.cleanup import ObjectCleaner, region_mask
from app.main import create_app
from app.schemas import Crop


class FakeCleaner:
    def status(self):
        return {"inpainting_installed": True, "inpainting_cached": True}

    def detect(self, image, threshold, queries):
        return [{"region": {"x": 10, "y": 10, "width": 12, "height": 8}, "score": .7, "label": queries[0]}]

    def inpaint(self, image, regions):
        mask = region_mask(image.size, regions)
        return Image.composite(Image.new("RGBA", image.size, "red"), image, mask)


def test_cleanup_preview_apply_undo_reset_and_export(tmp_path):
    source = io.BytesIO()
    Image.new("RGBA", (100, 80), "#506050").save(source, "PNG")
    with TestClient(create_app(tmp_path / "cleanup", cleaner=FakeCleaner())) as client:
        b = client.post("/api/batches", files={"files": ("device.png", source.getvalue())}).json()
        bid, iid = b["id"], b["images"][0]["id"]
        client.post(f"/api/batches/{bid}/process", json={})
        for _ in range(200):
            b = client.get(f"/api/batches/{bid}").json()
            if b["status"] != "processing":
                break
            time.sleep(.01)
        prefix = f"/api/batches/{bid}/images/{iid}"
        current = client.get(prefix + "/current").content
        found = client.post(prefix + "/cleanup/detect", json={"revision": 1}).json()
        assert len(found["suggestions"]) == 1
        assert client.get(prefix + "/current").content == current
        r = client.post(prefix + "/cleanup/preview", json={"revision": 1, "regions": [found["suggestions"][0]["region"]]})
        assert r.status_code == 200, r.text
        preview = r.json()["preview_id"]
        assert client.get(prefix + "/current").content == current  # preview does not apply
        image = Image.open(io.BytesIO(client.get(prefix + f"/cleanup/previews/{preview}").content))
        assert image.getpixel((11, 11)) == (255, 0, 0, 255)
        assert image.getpixel((0, 0)) == (80, 96, 80, 255)
        applied = client.post(prefix + "/cleanup/apply", json={"revision": 1, "preview_id": preview})
        assert applied.status_code == 200 and applied.json()["images"][0]["revision"] == 2
        assert client.post(prefix + "/cleanup/apply", json={"revision": 1, "preview_id": preview}).status_code == 409
        assert client.get(prefix + f"/cleanup/previews/{preview}").status_code == 409
        exported = client.get(f"/api/batches/{bid}/export")
        with zipfile.ZipFile(io.BytesIO(exported.content)) as z:
            assert json.loads(z.read("manifest.json"))["images"][0]["object_cleanup"] is True
        undone = client.post(prefix + "/undo", json={"reviewed": False, "revision": 2})
        assert undone.status_code == 200 and not undone.json()["images"][0]["cleanup_applied"]
        assert client.get(prefix + "/current").content == current
        assert client.post(prefix + "/cleanup/preview", json={"revision": 3, "regions": [{"x": 95, "y": 0, "width": 10, "height": 8}]}).status_code == 400
        assert client.post(prefix + "/cleanup/preview", json={"revision": 3, "regions": [{"x": 0, "y": 0, "width": 100, "height": 80}]}).status_code == 400


def test_missing_models_and_region_validation(tmp_path, monkeypatch):
    from app import cleanup
    monkeypatch.setattr(cleanup, "LAMA_PATH", tmp_path / "missing.onnx")
    cleaner = ObjectCleaner()
    with pytest.raises(ValueError, match="local LaMa setup"):
        cleaner.inpaint(Image.new("RGBA", (100, 100)), [Crop(x=10, y=10, width=10, height=10)])
    with pytest.raises(ValueError, match="40%"):
        region_mask((100, 100), [Crop(x=0, y=0, width=100, height=100)])
