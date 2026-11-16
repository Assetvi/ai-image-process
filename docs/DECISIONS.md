# Architecture and design decisions

## Implementation status

The implementation was written to a local checkout. Its 10 backend tests and production frontend build passed on November 16, 2026. The computer disconnected before the complete source upload. This repository currently contains the documentation; the application source and demo assets still need to be uploaded from that checkout. A live browser review and real-model inference were not completed.

No production throughput or model-quality claim is made for this reconstruction. It independently implements a described workflow without including employer code, internal systems, company images, credentials, user uploads, or downloaded weights.

## Workflow

Inspect uploaded images, flag only those needing background removal, run one batch action that crops every pending image and applies AI only to flagged images, inspect and correct outputs, then download one ZIP for an existing catalog upload workflow.

## Component choices

| Element | Choice | Reason | Tradeoff |
| --- | --- | --- | --- |
| Backend language | Python 3.11–3.13 | Direct access to Pillow, rembg, and ONNX Runtime; image operations and inference share one language. | A second language is needed for the browser UI. |
| API | FastAPI and Pydantic | Multipart uploads, validated edit coordinates, explicit schemas, generated API documentation. | Types do not replace pixel-level validation and file limits. |
| Frontend language | TypeScript | Makes image states, crop rectangles, brush strokes, and API payloads explicit. | Requires compilation and runtime server validation. |
| UI | React | Coordinates batch state, asynchronous processing, image loading, and edit drafts. | More setup than a simple HTML form. |
| Build | Vite | Fast development proxy and a static production build served by Python. | Node is required for building, although the finished app needs only Python. |
| Styling | Plain CSS | Direct control over a responsive editing workspace with few dependencies. | Styles need deliberate organization as the UI grows. |
| Icons | lucide-react | Consistent editing controls paired with labels and tooltips. | Retains the upstream software license. |
| Segmentation | Pretrained U²-Net through rembg | Practical local foreground segmentation without paid APIs, LLM prompts, or training data. | White details, glass, shadows, and fine edges still require human review. |
| Inference runtime | ONNX Runtime | CPU operation by default and optional compatible NVIDIA CUDA provider. | GPU installation also depends on CUDA/cuDNN compatibility. |
| AI selection | Per-image flag, initially off | Avoids changing already-clean product photos and avoids unnecessary inference. | A human still decides what needs segmentation. |
| Model download | Explicit setup step, weights excluded from Git | Keeps the public repository small and separates setup traffic from local image inference. | Initial setup needs Internet access and roughly 176 MB for U²-Net. |
| Model lifetime | One lazy, reusable session | Avoids repeatedly loading weights; crop-only workflows can work without AI dependencies. | The first AI job has initialization latency. |
| Pixel operations | Pillow on the server | Crops, brushes, and output use source-resolution pixels. | Large images consume RAM, so input pixel limits matter. |
| Preview | Browser canvas capped at 1800 px | Responsive inspection and brush feedback. | Preview rasterization can differ slightly at pixel boundaries. |
| Persistence | SQLite metadata and local PNG files | No separate database service; batches survive server restarts. | No accounts, shared-team access, encryption-at-rest, or automatic retention. |
| Processing | One executor worker and one server process | Bounds inference concurrency and coordinates file edits. | A shared multiuser service would need a durable queue and isolation. |
| Original preservation | Separate decoded original and editable working image | Restore can recover actual source RGBA pixels after a segmentation mistake. | Additional disk usage; restoring outside the object also restores its background. |
| Undo | Draft stroke undo and up to 10 saved snapshots | Straightforward recovery, including saved edits after reload. | More disk usage than sparse edit deltas. |
| Export | PNGs plus JSON manifest in ZIP | Lossless details, optional transparency, one download for existing upload systems. | PNGs can be large; browser ZIP downloads currently buffer the response. |
| Output backgrounds | White or transparent | Supports common catalog output and downstream compositing. | Transparent export does not remove a background from an unflagged source. |
| Tests | Pixel operations plus API workflow tests | Verifies selective AI calls, crop, restore, erase, undo, approval, ZIP contents, invalid uploads, stale edits, and recovery. | A deterministic model substitute does not measure real segmentation quality. |

## Processing and correction

1. Decode JPEG, PNG, or WebP, normalize EXIF orientation, strip metadata, and save decoded PNG originals under generated UUIDs. Reject unsupported/animated formats and oversized input. The limits are 200 files, 20 MB per file, 500 MB per batch, and 24 megapixels per image.
2. Record selective background-removal flags. Processing returns while a local worker handles queued images.
3. Start pending/failed images from their original. Flagged images receive a segmentation alpha mask multiplied by their source alpha, so existing transparent pixels are not made opaque by inference.
4. Compute crop bounds from alpha for transparent images or a configurable near-white threshold for opaque images. Add bounded edge padding. If no clear foreground is found, keep the original bounds and warn.
5. Allow a human to compare the original and processed image, restore source pixels, erase alpha, or draw a crop rectangle. Save at source resolution. Every edit clears approval.
6. Reject stale image revisions from another tab. Preserve completed images during batch retries. Reprocessing an image whose flag changed starts from the original and clears that image's edits.
7. Require all images to finish successfully before export. Optionally include only approved images. Include filenames, dimensions, AI flags, and approval states in the manifest.

Cropping changes bounds rather than recoloring product pixels. A white-threshold heuristic cannot guarantee correct bounds for every pale or transparent object; manual crop is part of the intended workflow.

## Interface choices

| Element | Purpose |
| --- | --- |
| Three-stage progress strip | Explain add → choose/process → review/export at a glance. |
| Image library on the left | Keep names, AI flags, review status, and navigation visible. |
| Large central editor | Give edge inspection and near-white product details most of the space. |
| Settings on the right | Keep crop options and export controls near their actions. |
| Original/processed toggle | Make accidental product-detail loss easy to spot. |
| Restore, erase, and crop | Address imperfect segmentation and failed automatic crop directly. |
| Explicit Save | Let the operator preview, undo, or discard draft edits before writing a new revision. |
| Approval separate from processing | Distinguish computation completion from human inspection. |
| Visible failures and blocked export | Prevent a ZIP from quietly omitting failed images. |
| Neutral surfaces with green primary actions | Keep attention on the product image and the next meaningful action. |
| Responsive panels | Reflow on smaller screens while prioritizing desktop editing. |

## Operation and boundaries

The app is designed for one trusted local operator, bound to loopback with one Python process. It rejects unexpected hosts and cross-origin writes, sanitizes and deduplicates export names, omits EXIF, limits image sizes, and never uses client paths for storage.

SQLite connections are explicitly closed, including on Windows. PNG writes use a temporary file and replacement. Metadata transactions and image-file writes are separate; a hard crash can leave them out of sync. Interrupted processing becomes a retryable error, preserving originals.

Uploaded images, database files, undo snapshots, environment files, model weights, build output, dependencies, and temporary working data are excluded from Git. The application is not configured as an Internet-facing upload service.

## Planned source layout

| Path | Responsibility |
| --- | --- |
| `app/main.py` | API, worker orchestration, image editing, approval, media, ZIP export. |
| `app/imaging.py` | Decode/orientation, crop bounds, brushes, filename handling. |
| `app/ai.py` | Local model setup state, session reuse, segmentation alpha. |
| `app/store.py` | SQLite metadata and interrupted-job recovery. |
| `app/schemas.py` | Runtime request validation and editing limits. |
| `frontend/src/App.tsx` | Batch workflow, polling, flags, settings, export. |
| `frontend/src/ImageEditor.tsx` | Canvas preview, crop drawing, brush drafts, comparison, zoom. |
| `scripts/generate_samples.py` | Reproducible generic sample illustrations. |
| `tests/` | Image and API checks without downloading model weights. |

These files were present in the local checkout but are not yet published in this repository.
