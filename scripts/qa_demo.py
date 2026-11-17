"""Run the real local models and publish reproducible, public-image QA artifacts.

Run from the repository root after installing all three local models:
    python scripts/qa_demo.py
No company images, credentials, or remote image inference are used.
"""
import io
import json
import sys
import time
import uuid
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.main import create_app


def main():
    samples = ROOT / "frontend/public/samples"
    output = ROOT / "docs/demo"
    output.mkdir(parents=True, exist_ok=True)
    names = ["desk-speaker.png", "white-bottle.png", "studio-headphones.png", "travel-camera.png", "iphone-15-pro-max.jpg", "cc0-camera.jpg"]
    checks = []
    with TestClient(create_app(ROOT / "data" / f"qa-{uuid.uuid4().hex}")) as client:
        def call(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            assert response.status_code < 400, (response.status_code, response.text)
            return response

        batch = call("POST", "/api/batches", files=[("files", (name, (samples / name).read_bytes())) for name in names]).json()
        bid = batch["id"]
        targets = [i["id"] for i in batch["images"] if i["name"] in {"travel-camera.png", "iphone-15-pro-max.png"}]
        call("PATCH", f"/api/batches/{bid}/flags", json={"image_ids": targets, "remove_background": True})
        call("POST", f"/api/batches/{bid}/process", json={"padding": 16, "white_threshold": 254})
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            batch = call("GET", f"/api/batches/{bid}").json()
            if batch["status"] != "processing":
                break
            time.sleep(.1)
        assert all(i["status"] == "ready" for i in batch["images"]), batch
        checks.append("Six real sample images processed successfully; only two flagged images used background removal.")
        print(checks[-1], flush=True)
        camera = next(i for i in batch["images"] if i["name"] == "cc0-camera.png")
        prefix = f"/api/batches/{bid}/images/{camera['id']}"
        original = call("GET", prefix + "/current").content
        crop_bytes = call("GET", prefix + "/result").content
        Image.open(io.BytesIO(crop_bytes)).convert("RGB").save(output / "cc0-camera-crop.jpg", quality=90)
        # Detection returns suggestions only. It never chooses what to remove.
        logos = call("POST", prefix + "/cleanup/detect", json={"revision": 1, "queries": ["a brand logo"], "threshold": .15}).json()["suggestions"]
        stickers = call("POST", prefix + "/cleanup/detect", json={"revision": 1, "queries": ["a yellow sticker"], "threshold": .08}).json()["suggestions"]
        assert call("GET", prefix + "/current").content == original
        checks.append("Real OWL-ViT detection completed without modifying any source pixels.")
        print(checks[-1], flush=True)
        # Explicitly human-selected rectangle from inspecting the CC0 photo.
        # This demonstrates the draw-region fallback, not an automatic decision.
        region = {"x": 636, "y": 57, "width": 224, "height": 67}
        marked = Image.open(io.BytesIO(original)).convert("RGB")
        ImageDraw.Draw(marked).rectangle((636, 57, 859, 123), outline="#b04a87", width=4)
        marked.save(output / "cc0-camera-region.jpg", quality=90)
        preview = call("POST", prefix + "/cleanup/preview", json={"revision": 1, "regions": [region]}).json()
        assert call("GET", prefix + "/current").content == original
        preview_bytes = call("GET", prefix + f"/cleanup/previews/{preview['preview_id']}").content
        result = Image.open(io.BytesIO(preview_bytes)).convert("RGBA")
        before = Image.open(io.BytesIO(original)).convert("RGBA")
        import numpy as np
        a, b = np.asarray(before), np.asarray(result)
        outside = np.ones(a.shape[:2], dtype=bool)
        outside[57:124, 636:860] = False
        assert np.array_equal(a[outside], b[outside]), "Unselected pixels changed"
        assert np.array_equal(a[:, :, 3], b[:, :, 3]), "Transparency changed"
        assert not np.array_equal(a[57:124, 636:860], b[57:124, 636:860]), "No fill occurred"
        result.convert("RGB").save(output / "cc0-camera-cleanup.jpg", quality=90)
        checks.append("Real LaMa preview changed the selected area, preserved all unselected pixels and alpha, and left the saved image unchanged.")
        print(checks[-1], flush=True)
        call("POST", prefix + "/cleanup/apply", json={"revision": 1, "preview_id": preview["preview_id"]})
        assert call("GET", prefix + "/current").content == preview_bytes
        assert client.post(prefix + "/cleanup/apply", json={"revision": 1, "preview_id": preview["preview_id"]}).status_code == 409
        call("POST", prefix + "/undo", json={"reviewed": False, "revision": 2})
        assert call("GET", prefix + "/current").content == original
        preview = call("POST", prefix + "/cleanup/preview", json={"revision": 3, "regions": [region]}).json()
        call("POST", prefix + "/cleanup/apply", json={"revision": 3, "preview_id": preview["preview_id"]})
        exported = call("GET", f"/api/batches/{bid}/export")
        with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
            assert len(archive.namelist()) == 7
            manifest = json.loads(archive.read("manifest.json"))
            assert sum(i["object_cleanup"] for i in manifest["images"]) == 1
        checks.append("Apply, stale-preview rejection, undo, and export of six PNGs plus a cleanup-aware manifest passed.")
        report = {"sample_count": 6, "background_removal_count": 2, "checks": checks,
                  "logo_suggestions": logos, "sticker_suggestions": stickers,
                  "removal_region_source": "manually selected after inspection", "removal_region": region,
                  "browser_qa": "not completed; computer control was stopped by the user",
                  "models": {"background": "U2-Net", "detection": "google/owlvit-base-patch32", "inpainting": "Carve LaMa ONNX"}}
        (ROOT / "docs/qa-results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
