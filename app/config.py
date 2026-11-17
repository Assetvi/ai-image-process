import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("IMAGE_PROCESS_DATA", ROOT / "data")).resolve()
MODEL_DIR = Path(os.environ.get("U2NET_HOME", ROOT / "models")).resolve()
os.environ.setdefault("U2NET_HOME", str(MODEL_DIR))
MODEL_NAME = "u2net"  # Fixed local model; no client-provided paths or remote inference.
PORT = int(os.environ.get("IMAGE_PROCESS_PORT", "8765"))
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_BATCH_BYTES = 500 * 1024 * 1024
MAX_FILES = 200
MAX_PIXELS = 24_000_000
