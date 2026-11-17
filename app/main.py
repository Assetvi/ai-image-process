import io
import json
import logging
import shutil
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

from .ai import BackgroundRemover
from .cleanup import ObjectCleaner
from .config import DATA_DIR, MAX_BATCH_BYTES, MAX_FILE_BYTES, MAX_FILES, PORT, ROOT
from .imaging import (
    apply_strokes,
    auto_box,
    decode_image,
    safe_filename,
    save_png,
    unique_name,
    validate_crop,
)
from .schemas import ApplyPreview, CleanupPreview, DetectRegions, Edit, Flags, Options, StrictModel
from .store import Store

logger = logging.getLogger(__name__)


class Reviewed(StrictModel):
    reviewed: bool
    revision: int


def create_app(data_dir: Path = DATA_DIR, remover=None, cleaner=None) -> FastAPI:
    store = Store(data_dir)
    engine = remover or BackgroundRemover()
    cleanup = cleaner or ObjectCleaner()
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="image-worker")

    @asynccontextmanager
    async def lifespan(_app):
        yield
        pool.shutdown(wait=True)

    api = FastAPI(title="Frame / local image processing", version="1.0.0", lifespan=lifespan)
    api.state.store = store
    api.state.engine = engine

    @api.middleware("http")
    async def local_boundary(request: Request, call_next):
        # Reject cross-origin writes, including form submissions to the loopback service.
        origin = request.headers.get("origin")
        allowed = {
            f"http://127.0.0.1:{PORT}",
            f"http://localhost:{PORT}",
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        }
        if request.method not in {"GET", "HEAD", "OPTIONS"} and origin and origin not in allowed:
            return JSONResponse({"detail": "Cross-origin writes are not allowed."}, status_code=403)
        host = request.url.hostname
        if host not in {"127.0.0.1", "localhost", "testserver"}:
            return JSONResponse({"detail": "Use this app on localhost."}, status_code=400)
        length = request.headers.get("content-length")
        if length:
            try:
                if int(length) > MAX_BATCH_BYTES + 1024 * 1024:
                    return JSONResponse({"detail": "Batch exceeds 500 MB."}, status_code=413)
            except ValueError:
                return JSONResponse({"detail": "Invalid content length."}, status_code=400)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' blob: data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'"
        )
        return response

    def batch_or_404(batch_id: str) -> dict:
        try:
            return store.get(batch_id)
        except KeyError:
            raise HTTPException(404, "Batch not found.") from None

    def item_or_404(batch: dict, image_id: str) -> dict:
        for item in batch["images"]:
            if item["id"] == image_id:
                return item
        raise HTTPException(404, "Image not found.")

    def editable(batch: dict):
        if batch["status"] == "processing":
            raise HTTPException(409, "Wait for batch processing to finish.")

    def render(folder: Path, item: dict):
        with Image.open(folder / "current.png") as image:
            result = image.crop(item["crop"])
            save_png(result, folder / "result.png")
            result.thumbnail((280, 280))
            save_png(result, folder / "thumbnail.png")

    def record_history(folder: Path, item: dict):
        snapshot = f"undo-{uuid.uuid4().hex}.png"
        shutil.copyfile(folder / "current.png", folder / snapshot)
        item["history"].append({"file": snapshot, "crop": item["crop"], "warning": item["warning"], "cleanup_applied": item.get("cleanup_applied", False)})
        while len(item["history"]) > 10:
            (folder / item["history"].pop(0)["file"]).unlink(missing_ok=True)

    def process(batch_id: str, target_ids: list[str]):
        started = time.monotonic()
        try:
            for image_id in target_ids:
                with store.lock:
                    batch = store.get(batch_id)
                    item = item_or_404(batch, image_id)
                    item["status"] = "processing"
                    store.put(batch)
                    folder = store.folder(batch_id, image_id)
                    flagged = item["remove_background"]
                    options = batch["options"]
                try:
                    with Image.open(folder / "original.png") as source:
                        original = source.convert("RGBA")
                    image = engine.remove(original) if flagged else original
                    crop, warning = auto_box(image, options["padding"], options["white_threshold"])
                    save_png(image, folder / "current.png")
                    with store.lock:
                        batch = store.get(batch_id)
                        item = item_or_404(batch, image_id)
                        for snapshot in item["history"]:
                            (folder / snapshot["file"]).unlink(missing_ok=True)
                        item.update(
                            status="ready",
                            error=None,
                            crop=crop,
                            warning=warning,
                            reviewed=False,
                            history=[],
                            revision=item["revision"] + 1,
                            cleanup_applied=False,
                        )
                        render(folder, item)
                        store.put(batch)
                except Exception as exc:
                    logger.exception("Image processing failed for image %s", image_id)
                    with store.lock:
                        batch = store.get(batch_id)
                        item = item_or_404(batch, image_id)
                        item.update(
                            status="error",
                            error=str(exc)
                            if isinstance(exc, ValueError)
                            else "Processing failed. Check the server log and retry.",
                        )
                        store.put(batch)
        finally:
            with store.lock:
                batch = store.get(batch_id)
                batch["status"] = "review"
                batch["elapsed_seconds"] = round(time.monotonic() - started, 2)
                store.put(batch)

    @api.get("/api/health")
    def health():
        return {
            "status": "ok",
            "ai": engine.status(),
            "cleanup": cleanup.status(),
            "limits": {
                "files": MAX_FILES,
                "file_mb": MAX_FILE_BYTES // 1024 // 1024,
                "batch_mb": MAX_BATCH_BYTES // 1024 // 1024,
                "megapixels": 24,
            },
        }

    @api.get("/api/batches")
    def recent():
        return store.recent()

    @api.post("/api/batches", status_code=201)
    def upload(files: list[UploadFile] = File(...)):
        if not 1 <= len(files) <= MAX_FILES:
            raise HTTPException(400, "Upload between 1 and 200 images.")
        batch_id = uuid.uuid4().hex
        batch = {
            "id": batch_id,
            "created_at": datetime.now(UTC).isoformat(),
            "status": "draft",
            "options": Options().model_dump(),
            "elapsed_seconds": None,
            "images": [],
        }
        total = 0
        used = {"manifest.json"}
        try:
            for uploaded in files:
                raw = uploaded.file.read(MAX_FILE_BYTES + 1)
                total += len(raw)
                if len(raw) > MAX_FILE_BYTES or total > MAX_BATCH_BYTES:
                    raise HTTPException(413, "Maximum 20 MB per image and 500 MB per batch.")
                try:
                    image = decode_image(raw)
                except ValueError as exc:
                    raise HTTPException(400, f"{safe_filename(uploaded.filename or 'image')}: {exc}") from exc
                image_id = uuid.uuid4().hex
                folder = store.folder(batch_id, image_id)
                folder.mkdir(parents=True)
                save_png(image, folder / "original.png")
                save_png(image, folder / "current.png")
                item = {
                    "id": image_id,
                    "name": unique_name(safe_filename(uploaded.filename or "image"), used),
                    "width": image.width,
                    "height": image.height,
                    "remove_background": False,
                    "status": "pending",
                    "crop": [0, 0, image.width, image.height],
                    "reviewed": False,
                    "revision": 0,
                    "history": [],
                    "error": None,
                    "warning": None,
                }
                render(folder, item)
                batch["images"].append(item)
            store.put(batch)
            return batch
        except Exception:
            # This directory is generated from our UUID, never a client path.
            shutil.rmtree(store.root / batch_id, ignore_errors=True)
            raise
        finally:
            for uploaded in files:
                uploaded.file.close()

    @api.get("/api/batches/{batch_id}")
    def get_batch(batch_id: str):
        return batch_or_404(batch_id)

    @api.patch("/api/batches/{batch_id}/flags")
    def flags(batch_id: str, payload: Flags):
        with store.lock:
            batch = batch_or_404(batch_id)
            editable(batch)
            targets = [item_or_404(batch, image_id) for image_id in payload.image_ids]
            for item in targets:
                if item["remove_background"] != payload.remove_background:
                    item.update(
                        remove_background=payload.remove_background,
                        status="pending",
                        reviewed=False,
                        error=None,
                    )
            batch["status"] = "draft" if any(i["status"] == "pending" for i in batch["images"]) else "review"
            store.put(batch)
            return batch

    @api.post("/api/batches/{batch_id}/process", status_code=202)
    def start_processing(batch_id: str, options: Options):
        with store.lock:
            batch = batch_or_404(batch_id)
            editable(batch)
            targets = [i for i in batch["images"] if i["status"] in {"pending", "error"}]
            if not targets:
                raise HTTPException(400, "All images are already processed.")
            if any(i["remove_background"] for i in targets):
                ai_status = engine.status()
                if not ai_status["installed"] or not ai_status["model_cached"]:
                    raise HTTPException(
                        409,
                        "Local AI is not set up. See README: install the AI extra, "
                        "then run python -m app.download_model. Crop-only images work immediately.",
                    )
            for item in targets:
                item["status"] = "queued"
            batch.update(status="processing", options=options.model_dump(), elapsed_seconds=None)
            store.put(batch)
            pool.submit(process, batch_id, [i["id"] for i in targets])
            return batch

    @api.get("/api/batches/{batch_id}/images/{image_id}/{kind}")
    def media(batch_id: str, image_id: str, kind: Literal["original", "current", "result", "thumbnail"]):
        batch = batch_or_404(batch_id)
        item_or_404(batch, image_id)
        return FileResponse(
            store.folder(batch_id, image_id) / f"{kind}.png",
            media_type="image/png",
            headers={"Cache-Control": "no-store"},
        )

    @api.post("/api/batches/{batch_id}/images/{image_id}/edit")
    def edit(batch_id: str, image_id: str, payload: Edit):
        with store.lock:
            batch = batch_or_404(batch_id)
            editable(batch)
            item = item_or_404(batch, image_id)
            if item["status"] != "ready":
                raise HTTPException(409, "Process this image before editing.")
            if payload.revision != item["revision"]:
                raise HTTPException(409, "Image changed in another tab. Refresh before editing.")
            folder = store.folder(batch_id, image_id)
            with Image.open(folder / "original.png") as source, Image.open(folder / "current.png") as now:
                original, current = source.convert("RGBA"), now.convert("RGBA")
            try:
                crop = validate_crop(payload.crop, current.size) if payload.crop else item["crop"]
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
            record_history(folder, item)
            image = original if payload.reset_original else apply_strokes(current, original, payload.strokes)
            warning = None
            if payload.reset_original:
                crop = [0, 0, image.width, image.height]
                item["cleanup_applied"] = False
            elif payload.auto_crop:
                crop, warning = auto_box(
                    image,
                    **{
                        "padding": batch["options"]["padding"],
                        "threshold": batch["options"]["white_threshold"],
                    },
                )
            save_png(image, folder / "current.png")
            item.update(crop=crop, warning=warning, reviewed=False, revision=item["revision"] + 1)
            render(folder, item)
            store.put(batch)
            return batch

    def ready_snapshot(batch_id: str, image_id: str, revision: int):
        # Called under the store lock; expensive inference runs outside it.
        batch = batch_or_404(batch_id)
        editable(batch)
        item = item_or_404(batch, image_id)
        if item["status"] != "ready" or revision != item["revision"]:
            raise HTTPException(409, "Process and reload this image before using cleanup.")
        folder = store.folder(batch_id, image_id)
        with Image.open(folder / "current.png") as source:
            current = source.convert("RGBA")
        return batch, item, folder, current

    @api.post("/api/batches/{batch_id}/images/{image_id}/cleanup/detect")
    def detect_regions(batch_id: str, image_id: str, payload: DetectRegions):
        with store.lock:
            _, _, _, image = ready_snapshot(batch_id, image_id, payload.revision)
        try:
            regions = cleanup.detect(image, payload.threshold, payload.queries)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        with store.lock:
            ready_snapshot(batch_id, image_id, payload.revision)
        return {"revision": payload.revision, "suggestions": regions}

    @api.post("/api/batches/{batch_id}/images/{image_id}/cleanup/preview")
    def preview_cleanup(batch_id: str, image_id: str, payload: CleanupPreview):
        with store.lock:
            _, _, folder, image = ready_snapshot(batch_id, image_id, payload.revision)
        try:
            result = cleanup.inpaint(image, payload.regions)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        with store.lock:
            ready_snapshot(batch_id, image_id, payload.revision)
            preview_id = uuid.uuid4().hex
            save_png(result, folder / f"preview-{preview_id}.png")
            (folder / f"preview-{preview_id}.json").write_text(json.dumps({"revision": payload.revision}), encoding="utf-8")
            # Bound retained preview disk usage per image, including abandoned drafts.
            previews = sorted(folder.glob("preview-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            for old in previews[3:]:
                old.with_suffix(".png").unlink(missing_ok=True)
                old.unlink(missing_ok=True)
        return {"preview_id": preview_id, "revision": payload.revision}

    def preview_path(folder: Path, preview_id: str, revision: int):
        if len(preview_id) != 32 or any(c not in "0123456789abcdef" for c in preview_id):
            raise HTTPException(404, "Preview not found.")
        meta = folder / f"preview-{preview_id}.json"
        if not meta.is_file():
            raise HTTPException(404, "Preview expired. Generate another preview.")
        if json.loads(meta.read_text(encoding="utf-8"))["revision"] != revision:
            raise HTTPException(409, "Image changed. Generate another cleanup preview.")
        return meta.with_suffix(".png")

    @api.get("/api/batches/{batch_id}/images/{image_id}/cleanup/previews/{preview_id}")
    def get_cleanup_preview(batch_id: str, image_id: str, preview_id: str):
        with store.lock:
            batch = batch_or_404(batch_id)
            item = item_or_404(batch, image_id)
            path = preview_path(store.folder(batch_id, image_id), preview_id, item["revision"])
            return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store"})

    @api.post("/api/batches/{batch_id}/images/{image_id}/cleanup/apply")
    def apply_cleanup(batch_id: str, image_id: str, payload: ApplyPreview):
        with store.lock:
            batch, item, folder, _ = ready_snapshot(batch_id, image_id, payload.revision)
            path = preview_path(folder, payload.preview_id, payload.revision)
            record_history(folder, item)
            with Image.open(path) as source:
                save_png(source, folder / "current.png")
            item.update(revision=item["revision"] + 1, reviewed=False, cleanup_applied=True)
            render(folder, item)
            store.put(batch)
            return batch

    @api.post("/api/batches/{batch_id}/images/{image_id}/undo")
    def undo(batch_id: str, image_id: str, payload: Reviewed):
        with store.lock:
            batch = batch_or_404(batch_id)
            editable(batch)
            item = item_or_404(batch, image_id)
            if payload.revision != item["revision"]:
                raise HTTPException(409, "Image changed in another tab. Refresh before undoing.")
            if item["status"] != "ready" or not item["history"]:
                raise HTTPException(409, "No saved edits to undo.")
            folder = store.folder(batch_id, image_id)
            snapshot = item["history"].pop()
            shutil.copyfile(folder / snapshot["file"], folder / "current.png")
            (folder / snapshot["file"]).unlink()
            item.update(
                crop=snapshot["crop"],
                warning=snapshot["warning"],
                reviewed=False,
                revision=item["revision"] + 1,
                cleanup_applied=snapshot.get("cleanup_applied", False),
            )
            render(folder, item)
            store.put(batch)
            return batch

    @api.patch("/api/batches/{batch_id}/images/{image_id}/review")
    def review(batch_id: str, image_id: str, payload: Reviewed):
        with store.lock:
            batch = batch_or_404(batch_id)
            editable(batch)
            item = item_or_404(batch, image_id)
            if item["status"] != "ready" or payload.revision != item["revision"]:
                raise HTTPException(409, "Process and reload the current image before approving.")
            item["reviewed"] = payload.reviewed
            store.put(batch)
            return batch

    @api.get("/api/batches/{batch_id}/export")
    def export(
        batch_id: str, background: Literal["white", "transparent"] = "white", reviewed_only: bool = False
    ):
        with store.lock:
            batch = batch_or_404(batch_id)
            editable(batch)
            if any(item["status"] != "ready" for item in batch["images"]):
                raise HTTPException(
                    409,
                    "Finish processing every image before exporting. Failed images "
                    "must be retried; they are never silently skipped.",
                )
            items = [i for i in batch["images"] if not reviewed_only or i["reviewed"]]
            if not items:
                raise HTTPException(400, "No approved images to export.")
            # Spool large archives to disk instead of keeping a whole batch in RAM.
            import tempfile

            archive = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
            manifest = {"application": "Frame", "background": background, "batch_id": batch_id, "images": []}
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as zipped:
                for item in items:
                    with Image.open(store.folder(batch_id, item["id"]) / "result.png") as source:
                        image = source.convert("RGBA")
                    if background == "white":
                        canvas = Image.new("RGBA", image.size, "white")
                        image = Image.alpha_composite(canvas, image).convert("RGB")
                    output = io.BytesIO()
                    image.save(output, format="PNG")
                    zipped.writestr(item["name"], output.getvalue())
                    manifest["images"].append(
                        {
                            "filename": item["name"],
                            "width": image.width,
                            "height": image.height,
                            "ai": item["remove_background"],
                            "reviewed": item["reviewed"],
                            "object_cleanup": item.get("cleanup_applied", False),
                        }
                    )
                zipped.writestr("manifest.json", json.dumps(manifest, indent=2))
            archive.seek(0)

        def chunks():
            try:
                while chunk := archive.read(1024 * 1024):
                    yield chunk
            finally:
                archive.close()

        return StreamingResponse(
            chunks(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="frame-{batch_id[:8]}.zip"'},
        )

    dist = ROOT / "frontend" / "dist"
    if dist.is_dir():
        api.mount("/", StaticFiles(directory=dist, html=True), name="frontend")
    return api


app = create_app()
