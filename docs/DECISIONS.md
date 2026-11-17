# Architecture and design decisions

## The workflow determines the architecture

The user makes a quick judgment about which images need segmentation. One action crops the batch and invokes AI only for flagged items. A human then inspects the result, restores lost product pixels, removes remaining background, or redraws a failed automatic crop. Finally the operator downloads a ZIP and uploads it using their existing catalog system.

This repository demonstrates that workflow independently. It does not integrate with any employer's admin system or claim a measured production time saving.

The optional cleanup extension adds local OWL-ViT suggestions and LaMa inpainting. Detection and alteration are separate actions: an operator enables cleanup, selects/deselects suggestions or draws rectangles, previews the proposed fill, then applies or discards it. The [UI design research](UI_DESIGN.md) explains the interface approach, and the [real-image demo](DEMO.md) shows the business decisions.

## Components and alternatives

| Component | Choice | Why | Tradeoff / alternative |
| --- | --- | --- | --- |
| Backend language | Python 3.11+ | Direct access to Pillow and local ML tooling. | A TypeScript-only app simplifies the stack, but moves segmentation and heavy pixel work into browser/WASM or another service. |
| Web API | FastAPI with Pydantic schemas | Reject malformed coordinates and unknown fields before editing files; provides API documentation. | Flask is smaller but needs more manual schema validation. |
| Frontend language | TypeScript | Makes batch status, brush strokes, crop rectangles, and response shapes explicit. | Types do not replace runtime server validation. |
| UI framework | React | Effects manage polling, canvas redraws, image loading, and pending edits. | Requires a build step; plain JavaScript could suit a much smaller interface. |
| Styling | Plain CSS | Keeps design readable and avoids another framework/runtime dependency. | Large stylesheets need deliberate organization. |
| Icons | lucide-react | Consistent, recognizable editing controls with text/tooltips. | Retains its upstream license. |
| Frontend build | Vite | Fast development with a same-origin API proxy; static production assets. | Node is needed to build, but not to serve the finished app. |
| Segmentation | rembg + U²-Net + ONNX Runtime | Reuses a pretrained segmentation model; no training pipeline, LLM, or external image service. | The general-purpose model can damage fine edges, white details, glass, and shadows. |
| AI selection | Explicit per-image flag, off by default | Avoids unnecessary inference and alteration of already-clean catalog images. | Operator still makes the initial judgment. |
| Logo suggestions | Optional local OWL-ViT, safetensors weights | Text queries and overlapping closer views can suggest marks without a service or specialist training set. | General-purpose detection can miss logos; model scores are not calibrated probabilities. |
| Object cleanup | Optional local LaMa ONNX, fixed 512 px model input | Inpaints a selected region using surrounding context; crop-based inference focuses resolution near the edit. | It synthesizes pixels and can invent detail, so preview and approval are required workflow steps. |
| Cleanup scope | Rectangle selections, maximum 20 regions and less than 40% of image area | Makes target areas explicit and preserves surrounding context. | Fine irregular masks may need several rectangles; ordinary erase/restore remain separate brush tools. |
| Preview lifetime | Revision-bound temporary files, at most three per image | Prevents applying a stale preview and bounds abandoned preview storage. | Expired previews must be regenerated. |
| Model lifetime | Lazy cached session | Loads once on first flagged job; crop-only mode works without installing AI. | First inference is slower and requires a separately downloaded model. |
| Concurrency | One executor worker and one server process | Bounds inference concurrency and serializes changes to shared files. | Unsuitable for a shared high-volume service without a real queue and per-job isolation. |
| Storage | SQLite JSON metadata + PNG files | Easy setup, restart persistence, no PostgreSQL/Redis/S3 requirements. | Local disk usage grows; no backup, quotas, users, or automatic retention policy. |
| Editor | Canvas preview and server-applied operations | Fast brush feedback; server writes original-resolution output. | The preview is capped at 1800 px and brush rasterization can differ slightly at pixel boundaries. |
| Undo | Preserved original plus up to 10 saved image snapshots | Straightforward recovery, including after a browser reload. | Uses more disk than storing only sparse edit deltas. |
| Export | PNG + manifest in a ZIP | Lossless product details, optional alpha, one download for existing tooling. | PNGs can be larger than JPEG; frontend download currently buffers the ZIP in browser memory. |

## Data flow

1. Upload validates byte/pixel counts and formats, normalizes EXIF orientation, strips metadata, and saves decoded original/working PNGs under generated UUIDs. Invalid multipart batches are rolled back.
2. Flags mark an image pending. Processing records queued/processing states and returns immediately while the local worker runs.
3. The worker starts from the preserved original, optionally computes a segmentation mask, multiplies it with original alpha, then calculates a crop rectangle. Existing transparent pixels cannot become opaque through inference.
4. Transparent images use alpha bounds for cropping; opaque images use a configurable near-white threshold. A no-foreground result keeps the original bounds and shows a warning. Cropping never paints white over product pixels.
5. Restore copies RGBA pixels from the preserved original. Erase changes alpha. Manual crop stores a rectangle in source coordinates. Revisions reject edits from a stale tab; every change clears approval.
6. Export rejects unfinished/failed items, optionally filters approved items, renders white or transparent PNGs, and records each included filename, dimensions, AI flag, and approval state in `manifest.json`.

## Interface decisions

| Element | Purpose |
| --- | --- |
| Three-stage strip | Makes add → choose/process → review/export understandable without a tutorial. |
| Batch library at left | Keeps filenames, flags, review status, and image navigation visible. |
| Large central editor | Leaves most space for edges and pale product details where review matters. |
| Settings at right | Groups batch crop settings and export choices near their actions. |
| Original/processed toggle | Gives an immediate reference when segmentation loses detail. |
| Restore/erase/crop tools | Directly addresses imperfect masks and failed automatic bounding boxes. |
| Explicit save | Allows several strokes to be previewed, undone, or discarded before writing a new image revision. |
| Approval separate from processing | A completed computation does not imply a person inspected it. |
| White/transparent output | Supports common catalog backgrounds and downstream compositing. |
| Error visibility | Prevents an apparently successful ZIP from quietly dropping failed items. |
| Responsive layout | Allows smaller screens to reflow panels; desktop remains the primary editing surface. |

## Reliability and privacy boundaries

The app rejects unexpected hosts and cross-origin writes, sanitizes export filenames, deduplicates names case-insensitively, limits input sizes, rejects animated formats, and omits EXIF in exports. User paths never determine storage paths. SQLite connections are explicitly closed to avoid Windows file locks. PNG writes use temporary files and replacement.

SQLite transactions and image-file replacement are separate operations; a hard crash at exactly the wrong moment can leave them out of sync. Interrupted processing is recovered as an error that can be retried from the original. This is a local workstation tool, not a hardened multiuser upload service. Model weights and input files are excluded from Git; the explicit download step contacts the model source but never submits user images.

CPU mode is the simplest default. GPU mode depends on external CUDA/cuDNN compatibility. No benchmark here establishes a GPU model, inference speed, mask quality target, or a guaranteed time for 100 images.

## Source map

| Path | Responsibility |
| --- | --- |
| `app/main.py` | API, worker orchestration, edits, approval, media, ZIP export. |
| `app/imaging.py` | Decode/orientation, crop bounds, brushes, filename handling. |
| `app/ai.py` | Local model setup status, session reuse, segmentation alpha. |
| `app/store.py` | SQLite metadata and restart recovery. |
| `app/schemas.py` | Runtime request validation and edit limits. |
| `frontend/src/App.tsx` | Batch workflow, polling, flags, settings, export. |
| `frontend/src/ImageEditor.tsx` | Canvas preview, crop drawing, brush drafts, comparison, zoom. |
| `scripts/generate_samples.py` | Reproducible original demo illustrations. |
| `tests/` | Pixel-level and API workflow checks without downloading model weights. |
