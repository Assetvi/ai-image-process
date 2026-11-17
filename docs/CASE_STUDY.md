# Business case: faster catalog image preparation

[Showcase](../README.md) | [Technical guide](TECHNICAL_GUIDE.md) | [Known issues](KNOWN_ISSUES.md)

## The business need

In an earlier role, I designed and built an internal product-image processing tool with AI-assisted coding. The team needed clean catalog images without repeating background removal and whitespace trimming by hand for each file. The tool had to fit the existing admin upload process and leave room for fast human correction.

The workflow was tailored to that need: inspect a batch, flag images that actually need background removal, crop the batch, review exceptions, and export one ZIP for the existing catalog system. Keeping that last step familiar avoided requiring a separate publishing system.

## Reported business results

These figures describe my reported experience with the earlier employer tool on batches of similar product photos. They include employee inspection and manual corrections.

| Measure | Earlier manual workflow | Earlier assisted workflow |
| --- | --- | --- |
| Batch size | About 100 similar product images | About 100 similar product images |
| Preparation time | About 30 minutes | Under 3 minutes |
| Time reduction | Baseline | More than 90% |
| Handoff | Prepared catalog assets | Reviewed batch exported for the existing upload process |

The reduction is derived from the reported times: 3 minutes is 10% of 30 minutes, so a result under 3 minutes represents more than 90% less preparation time. These are author-reported operational figures, not an independently audited benchmark.

This repository is a new public implementation. Its performance depends on image size, how many images need AI, model startup, hardware, and correction work. The earlier timing does not establish a 100-image speed for this rebuild or include a measured timing for its optional logo/object-cleanup extension. No exact GPU model is claimed.

## What the public rebuild demonstrates

| Business requirement | Implementation |
| --- | --- |
| Most of the work is repetitive. | Automatically crop the batch and run background AI only on flagged images. |
| Some pale products need correction. | Preserve originals; restore source pixels, erase leftovers, or draw a manual crop. |
| An approved brief may require removing a mark. | Suggest object/logo regions or let the operator draw them; preview, apply/discard, and undo. |
| Staff need a familiar handoff. | Export PNGs plus a manifest in one ZIP for the existing catalog upload process. |
| AI mistakes need a human decision. | Keep processing, preview, approval, and export as distinct actions. |

The production goal is reviewed catalog assets with unwanted backgrounds, excess margins, and approved logo/object regions cleaned up. Automatic detection cannot guarantee completely logo-free output. Operators confirm the intended marks are gone and genuine product detail remains before using an export.

## Evidence from this implementation

| Public-rebuild measure | Evidence |
| --- | --- |
| 12 backend tests | Passed locally; application behavior and pixel/revision checks. |
| 6 sample images | Real-model batch processing and ZIP assertions passed. |
| 2 selectively flagged images | Background removal ran only where selected in that batch. |
| Up to 200 images per batch | Configured upload limit; not a throughput benchmark. |
| Up to 10 saved edits per image | Undo history limit; originals remain separately preserved. |
| 1 ZIP handoff | PNG assets and a JSON manifest. |

The [QA report](QA.md) records the scope and limits. The [demo](DEMO.md) uses public images and original illustrations; it includes no employer source code, internal systems, or company photos.

## How I use AI assistance

I use AI assistance to prototype and iterate quickly while owning the workflow and verification. I review generated changes, develop small test cases for concrete behavior or observed bugs, fix the issue, rerun relevant checks, and inspect representative processed images. Separate tests cover application behavior and actual-model integration.

For example, a cleanup regression checks that unselected pixels and transparency stay unchanged. A stale-preview case confirms that an older result cannot overwrite a newer image revision. TypeScript compilation and the frontend production build catch interface-code errors. See [QA](QA.md) for the checks and remaining browser-review work.
