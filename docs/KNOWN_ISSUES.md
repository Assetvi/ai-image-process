# Known issues and the human recovery workflow

[Showcase](../README.md) | [Business case](CASE_STUDY.md) | [Technical guide](TECHNICAL_GUIDE.md)

The speed improvement comes from automating routine image preparation and giving people a short path to correct exceptions. AI remains optional. Most repetitive work can be processed as a batch; the operator checks the images that need attention rather than editing every file from scratch. No percentage of error-free images is claimed.

## Pale devices can lose genuine pixels

Background removal can mistake a white or nearly white part of a device for its background. Cables, pale edges, reflections, transparent surfaces, and small controls deserve a closer look. Automatic cropping can also produce a poor boundary when product and background are similar.

| Situation | Operator action |
| --- | --- |
| The existing background is already suitable. | Leave **Remove background** off; use crop-only processing. |
| A real product detail disappeared. | Compare **Original** and **Processed**, choose **Restore**, and paint the source pixels back. |
| Restoring also brought back unwanted background. | Use **Erase** carefully to remove the excess alpha. |
| Automatic cropping is wrong. | Use **Crop** to draw the intended bounds. |
| An edit made the result worse. | Undo it or reset to the preserved original. |

Restore copies actual original pixels, including original background when the brush crosses beyond the product. It does not reconstruct a missing feature from a prompt.

## Detection can miss a mark or select too much

The optional object/logo detector is general-purpose. It can return no suggestions, select the wrong object, or propose a rectangle that includes too much of the device. Model scores do not guarantee correctness. In the documented CC0 camera example, the detector returned no suitable region, so the sticker was selected manually.

1. Enable **Object & logo removal** only when cleanup is needed.
2. Inspect suggestions and deselect incorrect or oversized boxes.
3. Adjust the detection phrase/sensitivity, or choose **Draw region** and mark only the intended area.
4. Choose **Preview removal** and compare product detail before applying.
5. Discard a poor preview. If already applied, use undo or restore.

Detection only suggests regions. It does not automatically remove them. Cleanup edits preserve all source pixels outside selected rectangles and preserve the source alpha; the selected fill can still invent inaccurate detail.

## Production handoff

Check product edges, pale surfaces, intended logo/object regions, crop bounds, and the chosen output background. Approve reviewed assets, optionally export approved images only, and pass the ZIP into the existing catalog upload process.

The desired result is production-ready catalog imagery after this review. Neither this rebuild nor its model outputs establish a guarantee that every image is completely logo-free or that no manual correction is needed. Intentional edge padding is supported; whitespace trimming does not mean removing every white pixel around or within the product.

[QA scope and evidence](QA.md) | [Actual before/after examples](DEMO.md)
