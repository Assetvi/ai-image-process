"""Optional local detection and masked inpainting. No downloads during inference."""
import importlib.util
import os
from threading import Lock

from PIL import Image, ImageDraw

from .config import MODEL_DIR
from .schemas import Crop

LAMA_PATH = MODEL_DIR / "lama_fp32.onnx"
LAMA_URL = "https://huggingface.co/Carve/LaMa-ONNX/resolve/c3c0c9e46893/lama_fp32.onnx"
LAMA_SHA256 = "1faef5301d78db7dda502fe59966957ec4b79dd64e16f03ed96913c7a4eb68d6"
DETECTOR_PATH = MODEL_DIR / "logo-detector"
DETECTOR_REVISION = "cbc355fb364588351c5d51c7f74465e8e7ec6f72"


def region_mask(size: tuple[int, int], regions: list[Crop]) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    for r in regions:
        if r.x + r.width > size[0] or r.y + r.height > size[1]:
            raise ValueError("Removal regions must be inside the original image.")
        draw.rectangle((r.x, r.y, r.x + r.width - 1, r.y + r.height - 1), fill=255)
    if sum(mask.histogram()[1:]) > size[0] * size[1] * 0.4:
        raise ValueError("Select less than 40% of the image so AI has enough surrounding context.")
    if mask.getbbox() is None:
        raise ValueError("Draw or select at least one removal region.")
    return mask


class ObjectCleaner:
    def __init__(self):
        self._session = None
        self._detector = None
        self._processor = None
        self._lock = Lock()

    def status(self):
        return {
            "inpainting_installed": importlib.util.find_spec("onnxruntime") is not None,
            "inpainting_cached": LAMA_PATH.is_file(),
            "detector_installed": all(importlib.util.find_spec(n) is not None for n in ("torch", "transformers")),
            "detector_cached": all((DETECTOR_PATH / n).is_file() for n in ("model.safetensors", "config.json", "preprocessor_config.json", "tokenizer_config.json", "vocab.json", "merges.txt")),
            "model": "LaMa ONNX", "detector": "google/owlvit-base-patch32",
        }

    def inpaint(self, image: Image.Image, regions: list[Crop]) -> Image.Image:
        # Validate before loading optional dependencies or touching model files.
        mask = region_mask(image.size, regions)
        if not self.status()["inpainting_installed"] or not LAMA_PATH.is_file():
            raise ValueError("Object removal needs local LaMa setup. Run python -m app.download_cleanup_models.")
        import numpy as np
        import onnxruntime as ort
        with self._lock:
            if self._session is None:
                options = ort.SessionOptions()
                options.intra_op_num_threads = max(1, min(8, int(os.environ.get("IMAGE_PROCESS_AI_THREADS", "4"))))
                self._session = ort.InferenceSession(str(LAMA_PATH), sess_options=options, providers=["CPUExecutionProvider"])
            # Context around the selected area preserves detail on large products.
            left, top, right, bottom = mask.getbbox()
            pad = max(64, max(right - left, bottom - top))
            bounds = (max(0, left - pad), max(0, top - pad), min(image.width, right + pad), min(image.height, bottom + pad))
            patch = image.crop(bounds)
            patch_mask = mask.crop(bounds)
            rgb = Image.new("RGBA", patch.size, "white")
            rgb = Image.alpha_composite(rgb, patch).convert("RGB")
            values = np.asarray(rgb.resize((512, 512), Image.Resampling.LANCZOS), dtype=np.float32) / 255
            masks = np.asarray(patch_mask.resize((512, 512), Image.Resampling.NEAREST), dtype=np.float32) / 255
            prediction = self._session.run(None, {"image": values.transpose(2, 0, 1)[None], "mask": masks[None, None]})[0]
            filled = Image.fromarray(np.clip(prediction[0].transpose(1, 2, 0), 0, 255).astype("uint8"))
            filled = filled.resize(patch.size, Image.Resampling.LANCZOS).convert("RGBA")
            # Keep every unselected pixel and the original transparency exactly.
            filled.putalpha(patch.getchannel("A"))
            result = image.copy()
            result.paste(Image.composite(filled, patch, patch_mask), bounds[:2])
            return result

    def detect(self, image: Image.Image, threshold: float, queries: list[str]) -> list[dict]:
        status = self.status()
        if not status["detector_installed"] or not status["detector_cached"]:
            raise ValueError('Logo suggestions need pip install -e ".[detect]" and python -m app.download_cleanup_models --detector. You can draw removal regions without detection.')
        import torch
        from transformers import OwlViTForObjectDetection, OwlViTProcessor
        torch.set_num_threads(max(1, min(8, int(os.environ.get("IMAGE_PROCESS_AI_THREADS", "4")))))
        with self._lock:
            if self._detector is None:
                self._processor = OwlViTProcessor.from_pretrained(DETECTOR_PATH, local_files_only=True)
                self._detector = OwlViTForObjectDetection.from_pretrained(DETECTOR_PATH, local_files_only=True, use_safetensors=True).eval()
            candidates = []
            views = [(0, 0, image.width, image.height)]
            if max(image.size) > 800:
                # Small printed marks disappear when a whole device is downscaled.
                # Overlapping views give the detector a closer look at those details.
                w, h = round(image.width * .6), round(image.height * .6)
                views += [(x, y, x+w, y+h) for x in (0, image.width-w) for y in (0, image.height-h)]
            for bounds in views:
                patch = image.crop(bounds).convert("RGB")
                inputs = self._processor(text=[queries], images=patch, return_tensors="pt")
                with torch.inference_mode():
                    outputs = self._detector(**inputs)
                found = self._processor.image_processor.post_process_object_detection(outputs=outputs, threshold=threshold, target_sizes=torch.tensor([[patch.height, patch.width]]))[0]
                for box, score, label in zip(found["boxes"].tolist(), found["scores"].tolist(), found["labels"].tolist()):
                    x, y = max(0, int(box[0]) + bounds[0] - 4), max(0, int(box[1]) + bounds[1] - 4)
                    right, bottom = min(image.width, int(box[2]) + bounds[0] + 5), min(image.height, int(box[3]) + bounds[1] + 5)
                    if right <= x or bottom <= y or (right-x)*(bottom-y) > image.width*image.height*.25:
                        continue
                    rect = {"x": x, "y": y, "width": right-x, "height": bottom-y}
                    candidates.append({"region": rect, "score": round(score, 3), "label": queries[label]})
            accepted = []
            for candidate in sorted(candidates, key=lambda r: r["score"], reverse=True):
                a = candidate["region"]
                duplicate = False
                for old in accepted:
                    b = old["region"]
                    intersection = max(0, min(a["x"]+a["width"], b["x"]+b["width"])-max(a["x"], b["x"])) * max(0, min(a["y"]+a["height"], b["y"]+b["height"])-max(a["y"], b["y"]))
                    union = a["width"]*a["height"] + b["width"]*b["height"] - intersection
                    if intersection / union > .4:
                        duplicate = True
                        break
                if not duplicate:
                    accepted.append(candidate)
                if len(accepted) == 20:
                    break
            return accepted
