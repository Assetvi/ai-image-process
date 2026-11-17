# Lean experiment: crop-padding safety

[Technical guide](../docs/TECHNICAL_GUIDE.md) | [QA evidence](../docs/QA.md) | [Proof source](Crop.lean) | [Trial results](results.json)

We tried Lean on the arithmetic at the end of `app/imaging.py::auto_box`. Once Pillow has found a valid foreground rectangle, the app expands it by the requested padding and clamps it to the image. This is a small, stable algorithm with useful mathematical properties.

## What Lean checked

The specification uses natural numbers. Its `left - padding` is saturating subtraction, corresponding to Python's `max(0, left - padding)` for nonnegative inputs. Its other endpoint is `min(extent, right + padding)`. The application validates nonnegative padding and receives valid half-open bounds from Pillow.

| Theorem | Property, under its explicit input assumptions |
| --- | --- |
| `axis_safety` | A nonempty detected interval stays nonempty, contains the detected interval, and ends within the image. |
| `foreground_retained` | Every pixel coordinate inside the detected interval remains inside the padded crop. |
| `zero_padding` | Zero padding leaves valid bounds unchanged. |
| `padding_monotone` | Increasing padding cannot shrink the crop. |
| `rectangle_foreground_retained` | Combining the horizontal and vertical calculations retains every pixel coordinate inside the detected rectangle. |

These theorems quantify over all natural-number inputs satisfying their hypotheses. They are not limited to the finite fixtures below. Lean 4.19.0 checked the proofs; no admitted proofs or custom axioms are used. The runner audits theorem dependencies against Lean's standard `propext`, `Classical.choice`, and `Quot.sound` assumptions.

## Connecting the specification to Python

The running application still uses Python and Pillow. This is a manually reviewed Lean translation of its padding arithmetic, not a compiler-verified translation or a proof of the Python interpreter, Pillow, or the full application.

`scripts/check_lean_crop.py` asks the Lean program to emit 7,644 intervals: extents 1 through 12, every valid nonempty interval in each extent, and padding 0 through 20. It compares these outputs with actual `auto_box` calls on both image orientations and both foreground branches:

- A white foreground with transparent surrounding pixels, exercising alpha-based bounds.
- A dark foreground on opaque white, exercising color-threshold bounds.

That produces **30,576 real Pillow comparisons**. These are finite conformance checks, separate from the universal Lean proofs. They help detect a mismatch between the specification and the application's behavior, but do not close the translation gap for every possible input.

The first fixture design made some fully opaque white images and unexpectedly exercised the app's ambiguous-foreground fallback. That was a fixture assumption error, not a crop-padding bug. The corrected transparent fixtures retain a transparent margin so the intended alpha branch is exercised.

## Results and negative control

| Check | Observed result |
| --- | --- |
| Lean theorems | 5 accepted by the proof checker |
| Admitted proofs / nonstandard axioms | None |
| Lean-to-Pillow comparisons | 30,576 passed |
| Deliberately wrong algorithm | Replacing saturating subtraction with addition was rejected by the proof checker |
| New production bugs found | None in this trial |
| Local verification time | About 2 seconds after toolchain setup; see the recorded run |

The rejected variant is an artificial negative control. It demonstrates that the properties can reject a relevant arithmetic mistake; it is not a discovered production defect. Its failed proof is expected and handled by the runner.

## Is it worth keeping?

**Useful as a small optional safeguard.** The proof states exactly what padding must preserve, covers arithmetic cases beyond a finite test set, and makes future changes reviewable. It adds no dependency or inference cost to the running application.

**Limited benefit for the biggest image-quality problems.** Retaining detected foreground is different from detecting the genuine product. A segmentation model can already have removed a pale device part before this calculation runs. A detector can miss a logo, select the wrong region, or overselect the product. These proofs cannot establish correct recognition, realistic inpainting, or completely logo-free output. Representative images, pixel assertions, and human review remain necessary.

The cost is maintaining another language, a pinned compiler, and a translation of the relevant arithmetic. Keep this scope small. Expanding Lean across the whole UI or neural inference pipeline would currently add substantial work without an established benefit. The trial supports a narrow safety claim, not a measured reduction in production defects or a claim that formal methods are always economical.

## Reproduce locally

Use the official [Lean 4.19.0 release](https://github.com/leanprover/lean4/releases/tag/v4.19.0), or an existing Lean/elan installation honoring [lean-toolchain](lean-toolchain). The proof uses Lean's standard library and does not require Mathlib. The compiler is an optional development tool, downloaded separately; it is not committed to this repository or required to run Frame.

For the proof alone, with the pinned toolchain available:

```powershell
cd formal
lean Crop.lean
cd ..
```

For the proof, image comparisons, and negative control, run from the repository root after installing the application's Python dependencies:

```powershell
.\.venv\Scripts\python.exe scripts/check_lean_crop.py --lean "C:\path\to\lean-4.19.0-windows\bin\lean.exe"
```

On macOS/Linux, use `.venv/bin/python` and the corresponding Lean executable. The script exits nonzero on failed proofs, unexpected assumptions, conformance mismatches, or an invalid negative control. It writes fresh results to ignored `work/lean-crop-results.json`. The checked-in [results.json](results.json) records this trial.

## References

- [Official Lean introduction](https://lean-lang.org/theorem_proving_in_lean4/Introduction/) explains precisely stated claims and checked proofs.
- [Official Lean release source](https://github.com/leanprover/lean4/releases/tag/v4.19.0).
- [Lauren Tan's talk and source transcript](https://ai.engineer/code/2026/talks/lauren-tan) motivated the experiment. Her presentation describes formal verification as an experimental additional layer; the 70% token figure is an anecdote, not our verification budget or a project requirement.
