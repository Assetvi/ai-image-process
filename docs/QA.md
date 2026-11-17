# QA report

## Scope

QA covers the batch workflow and the new optional logo/object-cleanup path. All image examples use original sample illustrations, a credited CC BY 4.0 phone photo, or the CC0 camera photo described in [asset notices](../THIRD_PARTY_NOTICES.md). No employer materials are used.

## AI-assisted development workflow

The author previously built a similar business workflow with AI-assisted coding. This public reconstruction makes the development and verification approach inspectable: use AI assistance for rapid implementation, review the changed logic, create focused test cases for a feature or discovered failure, fix the failure, and rerun the relevant checks. Follow those checks with representative-image processing and inspection of the resulting assets.

Small regression cases exercise concrete behavior rather than merely repeat implementation details. Examples include preserving unselected pixels during inpainting, rejecting a stale preview, restoring an earlier image revision, and confirming the exact ZIP contents. Model-substitute tests verify application behavior; separate real-model QA checks the integrated pipeline. A successful local run does not imply a completed browser review.

## Checks

Local results for this revision: **12 backend tests passed** and the TypeScript/Vite production build succeeded. The six-image real-model QA script also passed its pixel, revision, undo, and ZIP assertions. OWL-ViT returned no logo or sticker suggestions on this particular camera photo; the shown removal uses the documented manual rectangle.

| Check | Evidence / result |
| --- | --- |
| Backend regressions | Tests cover selective background AI, crop/restore/erase, duplicate names, invalid uploads, stale revisions, undo, export, and interrupted-job recovery. |
| Cleanup integration | Tests exercise detection without writes, preview without apply, preservation outside a selected area, apply, stale-preview rejection, undo, invalid/oversized regions, missing model setup, and export metadata. |
| Production build | `npm run build` checks TypeScript and builds the React interface. |
| Real segmentation | Six sample images are processed; only two are flagged for U²-Net. |
| Real detection | Local OWL-ViT runs against the CC0 camera. Empty suggestions are a legitimate outcome and are recorded, rather than treated as successful logo recognition. |
| Real inpainting | LaMa fills a manually selected sticker region in the real photo. Assertions verify that unselected pixels and the alpha channel are unchanged. |
| Apply and recovery | Preview leaves the saved image unchanged; apply updates it; repeating a stale apply is rejected; undo restores the exact previous working PNG. |
| ZIP contents | Six PNGs and a JSON manifest, including an `object_cleanup` field for each exported item. |

The machine-readable real-model results are in [qa-results.json](qa-results.json). Reproduce them after model setup with:

```powershell
python scripts/qa_demo.py
```

The script writes a new ignored local QA workspace and refreshes the documented demo outputs. Its removal rectangle is explicitly selected from inspecting the photo. It does not pretend the detector selected that area automatically.

## Optional Lean crop experiment

Five Lean theorems check crop-padding bounds, nonempty output, retention of already-detected foreground, zero-padding identity, and padding monotonicity. A separate runner compared 7,644 Lean intervals with the actual Pillow pipeline in two orientations and two foreground branches: **30,576 comparisons passed**. An intentionally wrong padding calculation was rejected by Lean. No production defect was discovered by this trial.

This proves properties of a manually translated arithmetic specification. It does not prove the Python implementation end to end or verify segmentation/detection accuracy. See the [experiment, tradeoffs, and reproduction steps](../formal/README.md) and [recorded results](../formal/results.json).

## Bugs and limitations found

| Finding | Resolution or limit |
| --- | --- |
| SQLite context managers did not close connections on Windows. | Explicit connection closure prevents locked database files during cleanup. |
| rembg's new model-cache layout differed from the old flat directory. | Readiness checks support both locations. |
| Model calls can finish after another tab edits an image. | Detection/preview recheck revisions after inference; apply rejects stale revisions and previews. |
| A changed selection could leave an old preview to apply. | Undo is disabled while previewing; discard the preview before changing regions. |
| Preview image loading could fail independently of inference. | The UI waits for image loading and reports failure before offering apply. |
| Small logos may disappear at full-image detector resolution. | Larger photos are examined as a whole and through overlapping closer views. Suggestions remain experimental. |
| Cleanup could alter the surrounding product unnecessarily. | Only pixels inside selected rectangles are composited back; source alpha is preserved. |
| Inpainting can invent plausible but inaccurate detail. | Preview and human approval remain separate; use undo/restore when needed. |
| Tiny labels and cramped toolbars reduce usability. | A readability/focus/responsive polish layer addresses these in code. Live visual validation remains outstanding. |

## Desktop screenshot and smoke check

A later desktop browser check loaded the six public sample images, flagged the camera illustration and phone for background removal, processed the batch to six ready images with zero errors, selected the real CC0 camera, and enabled its optional cleanup controls. The actual [workspace screenshot](screenshots/workspace.jpg) appears in the [technical guide](TECHNICAL_GUIDE.md). This is a limited smoke check, not a complete interaction review.

The README's cropped cleanup example was subsequently exported from the running app after previewing and applying the documented manual sticker rectangle. The screenshot shows the earlier state with that sticker still present.

## Outstanding verification

Earlier browser automation was stopped with physical Escape input. The later limited desktop smoke check does not complete mobile layout review, pointer-drawn regions/crops, keyboard navigation, or download-dialog verification. Automated tests and a successful production build are not a substitute for those checks. The machine-readable real-model report records the scope of its earlier API/model run.

No accuracy percentage or production throughput guarantee is claimed from these examples. In particular, an empty detection result demonstrates the need for manual region drawing; it is not evidence that no logo exists.
