from app import ai


def test_model_status_accepts_current_and_legacy_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(ai, "MODEL_DIR", tmp_path)
    engine = ai.BackgroundRemover()
    assert engine.status()["model_cached"] is False
    current = tmp_path / "models" / "u2net" / "u2net.onnx"
    current.parent.mkdir(parents=True)
    current.write_bytes(b"cache-path-test-only")
    assert engine.status()["model_cached"] is True
    current.unlink()
    (tmp_path / "u2net.onnx").write_bytes(b"legacy-cache-path-test-only")
    assert engine.status()["model_cached"] is True
