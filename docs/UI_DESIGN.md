# UI design: a focused product-image workspace

The interface applies ideas from Apple's Human Interface Guidelines to a browser-based tool: clear task hierarchy, familiar controls, readable content, restrained decoration, and reversible actions. It is an independent design, not an Apple product or a native macOS interface.

## Research and implementation

| Reference | Interpretation in this workspace | Concrete change |
| --- | --- | --- |
| [Apple HIG — Design principles](https://developer.apple.com/design/human-interface-guidelines/design-principles) | Keep the operator in control. | Background AI and object cleanup have separate optional controls. Detected regions require selection; inpainting requires preview and apply. |
| [Apple HIG — Design principles](https://developer.apple.com/design/human-interface-guidelines/design-principles) | Make mistakes recoverable. | Discard, undo, restore, preserved originals, and revision checks protect a human editing workflow. |
| [Apple HIG — Layout](https://developer.apple.com/design/human-interface-guidelines/layout) | Give content and primary actions a clear order. | Images on the left, a large editor in the center, batch settings/export on the right. Cleanup appears beside its editing context. |
| [Apple UI Design Dos and Don'ts](https://developer.apple.com/design/tips/) | Fit the screen and make text legible. | Responsive panel reflow, larger secondary text, larger controls on narrow screens, and wrapping toolbars. |
| [Apple HIG — Design principles](https://developer.apple.com/design/human-interface-guidelines/design-principles) | Keep the task apparent and feedback consistent. | Direct workspace headings, progress/error states, selected-region overlays, and an explicit preview-only message. |

The restrained direction uses neutral surfaces, system fonts, consistent spacing, one primary action treatment, and a limited accent palette. It retains labels and recovery controls that operators need. Advanced detection sensitivity is disclosed only when wanted.

## Interaction details

- **AI off by default:** a batch starts with background removal unflagged. Cleanup is a separate toggle.
- **Suggestions are not edits:** detection returns candidate boxes and model scores. Operators can select, deselect, or ignore them, and draw their own rectangles.
- **Preview is distinct from saving:** a temporary image shows what LaMa proposes. Applying changes the image revision and clears approval. Discarding does not alter saved pixels.
- **Consistent recovery:** saved cleanup edits participate in the same undo history as crop and brush edits. Restoring copies genuine source pixels.
- **Keyboard visibility:** links, buttons, inputs, and disclosure controls have visible focus outlines. Detection phrases and sensitivity use ordinary form controls. Drawing remains pointer-based.
- **Narrow screens:** controls wrap, settings stack, and touch targets increase. Desktop is still the primary intended editing surface.

## UI issues addressed

The earlier stylesheet included very small secondary labels. The polish layer increases those sizes and contrast. The header now names the task directly. Editor tools wrap rather than competing for a single narrow row. The cleanup panel makes its optional state and selection state visible.

Preview state is invalidated when image revisions change. Undo is disabled while a preview is active, preventing a changed selection from leaving an old preview available to apply. Failed preview image loading is reported instead of silently leaving the operator to apply unseen output.

## README presentation

The front README follows a restrained, content-first direction inspired by [Apple HIG design principles](https://developer.apple.com/design/human-interface-guidelines/design-principles): prioritize the useful content, use concise wording, and make the hierarchy clear. A simple title and business story lead into three impact figures and one real before/after comparison. Monochrome text, selective bold emphasis, generous spacing, and short captions keep attention on the result. Supporting document links appear once at the bottom.

Installation, running instructions, and the actual UI screenshot live in the [technical guide](TECHNICAL_GUIDE.md). Reported earlier-employer results are labeled separately from public-rebuild evidence in the [business case](CASE_STUDY.md).

[AppFlowy](https://github.com/AppFlowy-IO/AppFlowy/blob/main/README.md) and [Stable Diffusion WebUI](https://github.com/AUTOMATIC1111/stable-diffusion-webui) were also reviewed as examples of image-led project introductions and deeper documentation links. These are presentation references; this project uses its own wording, screenshots, and examples.

## Verification limit

TypeScript compilation and API/model QA were completed. A later desktop smoke check also verified loading examples, selective flags, processing, image selection, and enabling cleanup; the [actual screenshot](screenshots/workspace.jpg) documents that state. Mobile layout, pointer drawing, keyboard navigation, and download dialogs still need review. Earlier browser attempts were interrupted; the later screenshot does not establish that all browser QA is complete.
