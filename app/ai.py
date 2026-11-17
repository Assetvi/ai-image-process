"""Lazy, reusable local model session. Whitespace cropping needs no AI install."""

import importlib.util
import logging
from threading import Lock

from PIL import Image, ImageChops

from .config import MODEL_DIR, MODEL_NAME

logger = logging.getLogger(__name__)


class BackgroundRemover:
    def __init__(self):
        self._session = None
        self._lock = Lock()
        self.error = None

    def status(self) -> dict:
        return {
            "installed": importlib.util.find_spec("rembg") is not None,
            "model_cached": any(
                path.is_file()
                for path in (
                    MODEL_DIR / "models" / MODEL_NAME / f"{MODEL_NAME}.onnx",
                    MODEL_DIR / f"{MODEL_NAME}.onnx",  # Legacy flat rembg cache.
                )
            ),
            "model": MODEL_NAME,
            "providers": self._session.inner_session.get_providers() if self._session else [],
            "error": self.error,
        }

    def prepare(self) -> None:
        with self._lock:
            if self._session is not None:
                return
            if not self.status()["installed"]:
                raise ValueError('Install local AI first: pip install -e ".[ai]"')
            if not self.status()["model_cached"]:
                raise ValueError("Download the model first: python -m app.download_model")
            try:
                import onnxruntime as ort
                from rembg import new_session

                available = ort.get_available_providers()
                providers = [p for p in ["CUDAExecutionProvider", "CPUExecutionProvider"] if p in available]
                self._session = new_session(MODEL_NAME, providers=providers)
                self.error = None
            except Exception as exc:
                logger.exception("Local model initialization failed")
                self.error = "Local AI could not start. Check the server log and model setup."
                raise ValueError(self.error) from exc

    def remove(self, original: Image.Image) -> Image.Image:
        self.prepare()
        from rembg import remove

        prediction = remove(original.convert("RGB"), session=self._session, only_mask=True).convert("L")
        result = original.copy()
        # Never make a source transparent pixel opaque again through model inference.
        result.putalpha(ImageChops.multiply(prediction, original.getchannel("A")))
        return result
