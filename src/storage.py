from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def atomic_write_json(path: Path | str, data: dict | list) -> None:
    """Atomically writes JSON data to path using a temp file + os.replace.

    Creates parent directories if missing. Guarantees no partial write on failure.

    Args:
        path: Destination file path.
        data: JSON-serializable data structure.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
