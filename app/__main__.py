import uvicorn

from .config import PORT

if __name__ == "__main__":
    # One process owns one model session and one SQLite/file-edit lock.
    uvicorn.run("app.main:app", host="127.0.0.1", port=PORT, workers=1)
