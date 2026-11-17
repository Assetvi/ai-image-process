import io
import json
import time
import zipfile

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.main import create_app
from app.store import Store


class FakeRemover:
    """Deterministic segmentation seam; does not claim to test model quality."""

    def __init__(self):
        self.calls = 0

    def status(self):
        return {"installed": True, "model_cached": True, "model": "test", "providers": [], "error": None}

    def remove(self, image):
        self.calls += 1
        output = image.copy()
        alpha = Image.new("L", image.size, 0)
        ImageDraw.Draw(alpha).rectangle((20, 20, 79, 59), fill=255)
        # Simulate the real failure motivating manual restore: lost white product pixels.
        ImageDraw.Draw(alpha).rectangle((30, 30, 39, 39), fill=0)
        output.putalpha(alpha)
        return output


def png(color="white"):
    image = Image.new("RGBA", (100, 80), "white")
    ImageDraw.Draw(image).rectangle((20, 20, 79, 59), fill=color)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


@pytest.fixture
def workspace(tmp_path):
    engine = FakeRemover()
    app = create_app(tmp_path / "workspace", engine)
    with TestClient(app) as client:
        yield client, engine, app.state.store


def add(client, files=None):
    response = client.post(
        "/api/batches", files=files or [("files", ("product.jpg", png("#536449"), "image/png"))]
    )
    assert response.status_code == 201, response.text
    return response.json()


def process(client, batch, **options):
    response = client.post(f"/api/batches/{batch['id']}/process", json={"padding": 0, **options})
    assert response.status_code == 202, response.text
    for _ in range(200):
        current = client.get(f"/api/batches/{batch['id']}").json()
        if current["status"] != "processing":
            return current
        time.sleep(0.01)
    pytest.fail("Batch did not finish.")


def test_selective_ai_manual_restore_crop_undo_and_zip(workspace):
    client, engine, _ = workspace
    batch = add(client, [("files", ("same.jpg", png("#fcfcfc"))), ("files", ("same.png", png("#536449")))])
    batch_id = batch["id"]
    first, second = batch["images"]
    assert engine.calls == 0
    assert client.get(f"/api/batches/{batch_id}/export").status_code == 409
    client.patch(
        f"/api/batches/{batch_id}/flags", json={"image_ids": [first["id"]], "remove_background": True}
    )
    batch = process(client, batch)
    assert engine.calls == 1
    assert all(i["crop"] == [20, 20, 80, 60] for i in batch["images"])
    assert batch["images"][0]["name"] == "same.png"
    assert batch["images"][1]["name"] == "same-2.png"
    image_id = first["id"]
    prefix = f"/api/batches/{batch_id}/images/{image_id}"
    before = Image.open(io.BytesIO(client.get(prefix + "/current").content))
    assert before.getpixel((35, 35))[3] == 0
    payload = {
        "revision": 1,
        "strokes": [{"mode": "restore", "radius": 8, "points": [{"x": 0.35, "y": 0.4375}]}],
        "crop": {"x": 25, "y": 25, "width": 50, "height": 30},
    }
    response = client.post(prefix + "/edit", json=payload)
    assert response.status_code == 200, response.text
    restored = Image.open(io.BytesIO(client.get(prefix + "/current").content))
    assert restored.getpixel((35, 35)) == (252, 252, 252, 255)
    assert client.post(prefix + "/edit", json=payload).status_code == 409  # stale tab
    assert client.patch(prefix + "/review", json={"reviewed": True, "revision": 2}).status_code == 200
    response = client.get(f"/api/batches/{batch_id}/export?background=transparent&reviewed_only=true")
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert set(archive.namelist()) == {"same.png", "manifest.json"}
        exported = Image.open(archive.open("same.png"))
        assert exported.size == (50, 30)
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["images"][0]["reviewed"] is True
    response = client.post(prefix + "/undo", json={"reviewed": False, "revision": 2})
    assert response.status_code == 200
    item = response.json()["images"][0]
    assert item["revision"] == 3 and not item["reviewed"]
    assert item["crop"] == [20, 20, 80, 60]
    undone = Image.open(io.BytesIO(client.get(prefix + "/current").content))
    assert undone.getpixel((35, 35))[3] == 0
    original = Image.open(io.BytesIO(client.get(prefix + "/original").content))
    assert original.getpixel((35, 35))[3] == 255
    assert client.get(f"/api/batches/{batch_id}/images/{second['id']}/original").status_code == 200


def test_white_export_erase_reset_and_crop_validation(workspace):
    client, _, _ = workspace
    batch = process(client, add(client))
    item = batch["images"][0]
    prefix = f"/api/batches/{batch['id']}/images/{item['id']}"
    response = client.post(
        prefix + "/edit",
        json={"revision": 1, "strokes": [{"mode": "erase", "radius": 5, "points": [{"x": 0.5, "y": 0.5}]}]},
    )
    assert response.status_code == 200
    for background, expected in [("white", (255, 255, 255)), ("transparent", (83, 100, 73, 0))]:
        response = client.get(f"/api/batches/{batch['id']}/export?background={background}")
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            image = Image.open(archive.open(item["name"]))
            assert image.getpixel((30, 20)) == expected
    response = client.post(
        prefix + "/edit", json={"revision": 2, "crop": {"x": 90, "y": 0, "width": 20, "height": 10}}
    )
    assert response.status_code == 400
    response = client.post(prefix + "/edit", json={"revision": 2, "reset_original": True})
    assert response.status_code == 200
    assert response.json()["images"][0]["crop"] == [0, 0, 100, 80]


def test_invalid_upload_is_atomic_and_paths_are_sanitized(workspace):
    client, _, store = workspace
    response = client.post(
        "/api/batches", files=[("files", ("ok.png", png())), ("files", ("bad.png", b"not an image"))]
    )
    assert response.status_code == 400
    assert store.recent() == []
    assert not [p for p in store.root.iterdir() if p.is_dir()]
    batch = add(
        client,
        [
            ("files", ("../../outside.png", png("black"))),
            ("files", ("C:\\private\\OUTSIDE.jpg", png("black"))),
            ("files", ("CON.png", png("black"))),
        ],
    )
    assert [i["name"] for i in batch["images"]] == ["outside.png", "OUTSIDE-2.png", "_CON.png"]
    assert client.get("/api/batches/not-found").status_code == 404
    assert (
        client.post(
            "/api/batches", files=[("files", ("x.png", png()))], headers={"Origin": "https://example.com"}
        ).status_code
        == 403
    )
    assert client.get("/api/health", headers={"Host": "attacker.example"}).status_code == 400


def test_retry_does_not_replace_completed_edits_and_missing_ai_is_honest(workspace):
    client, engine, _ = workspace
    batch = add(client, [("files", ("one.png", png("black"))), ("files", ("two.png", png("black")))])
    batch = process(client, batch)
    first, second = batch["images"]
    prefix = f"/api/batches/{batch['id']}/images/{first['id']}"
    response = client.post(
        prefix + "/edit", json={"revision": 1, "crop": {"x": 30, "y": 30, "width": 25, "height": 20}}
    )
    assert response.status_code == 200
    client.patch(
        f"/api/batches/{batch['id']}/flags", json={"image_ids": [second["id"]], "remove_background": True}
    )
    engine.status = lambda: {"installed": False, "model_cached": False}
    assert client.post(f"/api/batches/{batch['id']}/process", json={}).status_code == 409
    engine.status = lambda: {"installed": True, "model_cached": True}
    batch = process(client, batch)
    assert engine.calls == 1
    assert batch["images"][0]["crop"] == [30, 30, 55, 50]
    assert batch["images"][0]["revision"] == 2


def test_failed_ai_prevents_incomplete_export(workspace):
    client, engine, _ = workspace
    batch = add(client)

    def fail(_image):
        raise ValueError("Model unavailable.")

    engine.remove = fail
    client.patch(
        f"/api/batches/{batch['id']}/flags",
        json={"image_ids": [batch["images"][0]["id"]], "remove_background": True},
    )
    batch = process(client, batch)
    assert batch["images"][0]["status"] == "error"
    assert client.get(f"/api/batches/{batch['id']}/export").status_code == 409


def test_restart_recovers_interrupted_work_without_losing_original(workspace):
    client, _, store = workspace
    batch = add(client)
    batch["status"] = "processing"
    batch["images"][0]["status"] = "queued"
    store.put(batch)
    reopened = Store(store.root).get(batch["id"])
    assert reopened["status"] == "review"
    assert reopened["images"][0]["status"] == "error"
    assert (store.folder(batch["id"], batch["images"][0]["id"]) / "original.png").exists()
