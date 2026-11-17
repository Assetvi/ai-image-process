"""Explicit one-time model download; never sends user images anywhere."""

from .config import MODEL_DIR, MODEL_NAME


def main():
    from rembg import new_session

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading/verifying {MODEL_NAME} in {MODEL_DIR} ...")
    new_session(MODEL_NAME, providers=["CPUExecutionProvider"])
    print("Local model ready. Start the app with python -m app.")


if __name__ == "__main__":
    main()
