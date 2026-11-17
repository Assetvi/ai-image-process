import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import RLock


class Store:
    """SQLite transactions persist metadata; callers serialize file and metadata edits with lock."""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()
        with self.connect() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS batches (id TEXT PRIMARY KEY, body TEXT NOT NULL)")
            for (body,) in connection.execute("SELECT body FROM batches").fetchall():
                batch = json.loads(body)
                if batch["status"] == "processing":
                    batch["status"] = "review"
                    for item in batch["images"]:
                        if item["status"] in {"processing", "queued"}:
                            item["status"] = "error"
                            item["error"] = "Server stopped during processing. Reprocess this batch."
                    connection.execute(
                        "UPDATE batches SET body=? WHERE id=?", (json.dumps(batch), batch["id"])
                    )

    @contextmanager
    def connect(self):
        # sqlite3's own context manager commits/rolls back but does not close.
        # Explicit closure matters on Windows, where open files cannot be removed.
        connection = sqlite3.connect(self.root / "batches.sqlite3")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def get(self, batch_id: str) -> dict:
        with self.lock, self.connect() as connection:
            row = connection.execute("SELECT body FROM batches WHERE id=?", (batch_id,)).fetchone()
            if row is None:
                raise KeyError("Batch not found.")
            return json.loads(row[0])

    def put(self, batch: dict) -> None:
        with self.lock, self.connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO batches VALUES (?, ?)", (batch["id"], json.dumps(batch))
            )

    def recent(self) -> list[dict]:
        with self.lock, self.connect() as connection:
            rows = connection.execute("SELECT body FROM batches ORDER BY rowid DESC LIMIT 20").fetchall()
        return [
            {"id": b["id"], "created_at": b["created_at"], "count": len(b["images"]), "status": b["status"]}
            for b in [json.loads(row[0]) for row in rows]
        ]

    def folder(self, batch_id: str, image_id: str) -> Path:
        # IDs only come from validated UUIDs already found in metadata.
        return self.root / batch_id / image_id
