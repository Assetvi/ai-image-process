"""Explicit model installation. Image inference never downloads or uploads data."""
import argparse
import hashlib
import urllib.request

from .cleanup import DETECTOR_PATH, DETECTOR_REVISION, LAMA_PATH, LAMA_SHA256, LAMA_URL


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--detector", action="store_true", help="Also download optional OWL-ViT detection weights")
    args = parser.parse_args()
    LAMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not LAMA_PATH.is_file():
        temporary = LAMA_PATH.with_suffix(".download")
        print("Downloading LaMa ONNX (~208 MB)...", flush=True)
        urllib.request.urlretrieve(LAMA_URL, temporary)
        if hashlib.sha256(temporary.read_bytes()).hexdigest() != LAMA_SHA256:
            raise ValueError("LaMa checksum mismatch; model was not installed.")
        temporary.replace(LAMA_PATH)
    if hashlib.sha256(LAMA_PATH.read_bytes()).hexdigest() != LAMA_SHA256:
        raise ValueError("Existing LaMa model has an unexpected checksum.")
    if args.detector:
        from huggingface_hub import snapshot_download
        snapshot_download("google/owlvit-base-patch32", revision=DETECTOR_REVISION, local_dir=DETECTOR_PATH,
                          allow_patterns=["*.json", "*.txt", "*.safetensors"])
    print("Cleanup model setup finished. Restart the server.")


if __name__ == "__main__":
    main()
