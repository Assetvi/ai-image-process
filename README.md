# Frame — AI Image Process

A local product-image workspace for a practical human-in-the-loop workflow: inspect a batch, flag only images needing AI background removal, crop all images, correct mistakes, and export one ZIP for an existing catalog upload system.

**Browse the code:** [Python backend](app/) · [React interface](frontend/src/) · [tests](tests/).

**See the business workflow:** [before/after image demonstrations](docs/DEMO.md) · [QA report](docs/QA.md) · [UI design research](docs/UI_DESIGN.md).

This is an independent implementation of that workflow. No company source code, internal systems, customer data, or company product photos are included.

## What works

- Upload JPEG, PNG, or WebP: up to 200 images, 20 MB each, 500 MB total, and 24 megapixels per image.
- Decide per image whether to remove its background. Unflagged images go through cropping only.
- Run local U²-Net inference through rembg and ONNX Runtime. No image-processing API keys or external inference services.
- Automatically trim outer whitespace or transparent borders, with adjustable padding and white threshold.
- Compare original and processed views; draw a manual crop rectangle; restore original pixels or erase with a brush.
- Optionally enable object/logo cleanup, ask the local detector for suggestions, select or deselect regions, or draw rectangles manually. Preview LaMa inpainting, then apply or discard it.
- Undo unsaved brush strokes and up to 10 saved edits per image. Reset to the original at any time after processing.
- Approve results, reopen recent batches, and export all images or only approved images.
- Export PNGs on white or transparent backgrounds plus a manifest. Failed images block export until fixed; they are never silently omitted.

## Run locally

Requirements: Python 3.11–3.13 and Node.js 22.12 or newer. Run commands from the repository root. Python 3.11 is the verified development version.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[ai,dev]"
cd frontend
npm install
npm run build
cd ..
.\.venv\Scripts\python.exe -m app.download_model
.\.venv\Scripts\python.exe -m app
```

Open **http://127.0.0.1:8765**. Keep this terminal running. Model setup is an explicit one-time download of approximately 176 MB; subsequent inference runs locally. Package installation and model setup require Internet access.

On macOS/Linux, replace `.\.venv\Scripts\python.exe` with `.venv/bin/python`. To use crop and manual-edit features without AI, install `".[dev]"` and omit the model download. AI-flagged processing will explain that setup is missing.

For frontend development, run `npm run dev` in `frontend` alongside the Python server. Vite proxies `/api` to port 8765. Rebuild the frontend before returning to the single-server setup. `IMAGE_PROCESS_PORT` can change the Python port; update the Vite proxy when using a custom port for development.

### Optional NVIDIA GPU

Use `pip install -e ".[gpu]"` in a separate environment instead of the CPU AI extra. Configure the CUDA/cuDNN versions required by your ONNX Runtime installation. The app prefers an available CUDA provider and otherwise uses CPU. Installing the GPU extra alone does not guarantee GPU execution; `/api/health` reports the providers after model initialization.

## Demo walkthrough

Click **Try an example batch**. It includes original speaker, white bottle, headphones, and camera illustrations plus a credited iPhone 15 Pro Max photo. Leave the clean images unflagged; flag the camera and phone, then process the batch. Inspect the output and use Crop, Restore, and Erase as needed before approving and exporting.

See [the demo guide](docs/DEMO.md) for a real-device example and human review steps. See [asset credits](THIRD_PARTY_NOTICES.md) for the source and license of any third-party demo photo.

## Why these components?

| Element | Decision and reason |
| --- | --- |
| Image-processing language | Python: mature Pillow, rembg, and ONNX Runtime support; keeps image algorithms and inference in one process. |
| API | FastAPI: explicit validated request schemas, multipart uploads, and generated API docs at `/docs`. |
| Interface | React and TypeScript: predictable batch/editor state and typed API payloads; useful for an editing workspace with several simultaneous controls. |
| Build tool | Vite: fast local development; ships a static build that Python can serve. |
| AI | Local pretrained U²-Net through rembg: practical segmentation without training data, paid APIs, or sending product photos elsewhere. |
| Human review | Selective flags, preserved originals, and manual correction: segmentation can remove white product details or leave unwanted background. |
| Image operations | Pillow on the server: edits and export use source-resolution pixels; the browser canvas is a preview. |
| Persistence | SQLite metadata and local PNG files: no separate database service and batches survive restarts. |
| Worker | One background processing worker: avoids loading several model sessions and oversubscribing GPU/RAM. |
| Export | PNGs in ZIP with JSON manifest: preserves details/transparency and fits a manual admin upload workflow. |
| UI design | Muted neutral surfaces, green actions, three workflow stages, and image/editor/settings columns: puts reviewing and correction at the center. |

[Architecture and tradeoffs](docs/DECISIONS.md) explains each choice, alternatives, data flow, limits, and failure behavior in more depth.

## Data and operation

### Object cleanup

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[ai,cleanup,detect,dev]"
.\.venv\Scripts\python.exe -m app.download_cleanup_models --detector
```

Restart the server. LaMa is approximately 208 MB; the optional OWL-ViT detector adds larger weights and PyTorch dependencies. The downloaded weights stay in ignored `models/`. Installation downloads models; inference reads local files only.

After processing an image, enable **Object & logo removal**. **Detect logos** provides suggestions; it does not change the picture. Enter a phrase such as a brand name and adjust sensitivity if needed. Select or deselect suggestions, or use **Draw region** and drag one or more rectangles on the image. **Preview removal** shows a proposed fill. **Apply removal** saves it and clears approval; **Discard preview** leaves the image unchanged. Disable the cleanup toggle to clear the region selection. Undo or restore original pixels if a result is wrong.

Automatic suggestions are experimental and can miss logos or select the wrong area. The model is a general-purpose detector, not a specialist logo recognizer. A preview can invent surface detail, so review it before approving catalog images. Background removal and object cleanup are independently optional. Ordinary erase removes transparency; cleanup synthesizes replacement pixels.

`data/` contains decoded originals, working images, undo snapshots, and a SQLite database. `models/` contains the separately downloaded model. Both are ignored by Git. `IMAGE_PROCESS_DATA` and `U2NET_HOME` can override those directories before starting Python. Images are not automatically deleted: stop the server and remove the appropriate local batch directory/database when you want to clear the workspace.

The service binds to loopback and is intended for one trusted local operator, with one Python server process. It has no user accounts, encryption-at-rest, or Internet hosting configuration. Do not expose it to a LAN or the public Internet. Cropping changes bounds rather than recoloring pixels; it cannot reliably identify very pale objects, transparent glass, complex shadows, or every background. Review those cases manually.

Reprocessing a pending image starts from its original and clears its saved edits. Completed images are skipped, preserving their corrections. Changing batch crop settings affects pending/failed images; use **Auto-crop again** on a completed image to apply the latest saved processing settings.

## Validation

```powershell
.\.venv\Scripts\python.exe -m pytest -q
cd frontend
npm run build
```

The workflow tests cover selective model calls, restoring lost white pixels, manual crop, erase, undo, review state, export contents, stale-edit rejection, invalid uploads, and restart recovery. They use a deterministic model substitute; they do not measure pretrained-model accuracy or prove a specific batch throughput. Real model quality requires inspecting representative product images.

Verification includes backend tests, a TypeScript/Vite production build, and real-model image processing. Run `python scripts/qa_demo.py` after local model setup to reproduce the six-image batch, detection requests, inpainting preview, pixel-preservation assertions, apply/undo checks, and ZIP export. See the [QA report](docs/QA.md) for results and verification limits.

## License

Project code and original sample illustrations: MIT. Third-party photos, libraries, and downloaded model weights retain their own licenses; see [notices](THIRD_PARTY_NOTICES.md).
