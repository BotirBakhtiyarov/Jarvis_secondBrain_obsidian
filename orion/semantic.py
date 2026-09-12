"""Optional semantic (vector) search backed by fastembed (ONNX, no torch).

The index is built via the ``reindex`` tool and stored in ``.orion_index/``.
Search only uses an existing index and a locally cached model — it never
downloads anything by itself (downloads happen only during reindex).
"""

import json
import os
from pathlib import Path

MODEL_NAME = "BAAI/bge-small-en-v1.5"
INDEX_DIR = ".orion_index"
LEGACY_INDEX_DIR = ".jarvis_index"


class SemanticIndex:
    def __init__(self, vault_root: Path):
        self.root = Path(vault_root)
        self.dir = self.root / INDEX_DIR
        self.legacy_dir = self.root / LEGACY_INDEX_DIR

    @staticmethod
    def is_available() -> bool:
        try:
            import fastembed  # noqa: F401

            return True
        except Exception:  # noqa: BLE001
            return False

    @staticmethod
    def model_cached() -> bool:
        """True when the model is already in the local cache (offline-safe check)."""

        cache = Path(
            os.environ.get(
                "FASTEMBED_CACHE_PATH",
                Path.home() / ".cache" / "fastembed",
            )
        )
        if not cache.exists():
            return False

        stem = MODEL_NAME.replace("/", "__")
        return (cache / stem).exists() or any(p.is_dir() for p in cache.iterdir() if stem in p.name)

    def _mark_disabled(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "disabled").touch()

    def _is_disabled(self) -> bool:
        return (self.dir / "disabled").exists()

    @staticmethod
    def _has(d: Path) -> bool:
        return (d / "vectors.npy").exists() and (d / "paths.json").exists()

    def _index_dir(self) -> Path | None:
        if not self._is_disabled() and self._has(self.dir):
            return self.dir
        if self._has(self.legacy_dir):
            return self.legacy_dir
        return None

    def has_index(self) -> bool:
        return self._index_dir() is not None

    def build(
        self,
        notes: list[tuple[str, str]],
        code_files: list[tuple[str, str]] | None = None,
        progress=None,
    ) -> None:
        """Build the index (may download the model on first run).

        *notes* — Obsidian note ``(relative_path, content)`` pairs.
        *code_files* — optional workspace code ``(relative_path, content)`` pairs
            to index alongside notes.  When provided, keyword + semantic search
            covers both code and notes.
        Optional ``progress(done, total)`` callback drives the UI bar.
        """

        import numpy as np
        from fastembed import TextEmbedding

        model = TextEmbedding(model_name=MODEL_NAME)

        combined: list[tuple[str, str]] = list(notes)
        if code_files:
            combined.extend(code_files)

        paths = [p for p, _ in combined]
        texts = [c[:4000] for _, c in combined]

        vectors: list = []
        batch_size = 64
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            for emb in model.embed(batch):
                vectors.append(np.asarray(emb, dtype=np.float32))
            if progress:
                progress(min(i + len(batch), len(texts)), len(texts))

        matrix = np.vstack(vectors) if vectors else np.zeros((0, 1), dtype=np.float32)

        self.dir.mkdir(parents=True, exist_ok=True)
        np.save(self.dir / "vectors.npy", matrix)
        (self.dir / "paths.json").write_text(
            json.dumps(paths, ensure_ascii=False), encoding="utf-8"
        )
        (self.dir / "disabled").unlink(missing_ok=True)

    def search(self, query: str, limit: int = 10) -> list[tuple[str, float]]:
        """Search using an existing index and a locally cached model.

        Returns ``[]`` when the index or model cache is missing — never
        downloads anything from the network.
        """

        import numpy as np
        from fastembed import TextEmbedding

        index_dir = self._index_dir()
        if index_dir is None or not self.model_cached():
            return []

        try:
            matrix = np.load(index_dir / "vectors.npy")
            paths = json.loads((index_dir / "paths.json").read_text(encoding="utf-8"))

            if matrix.shape[0] == 0:
                return []

            model = TextEmbedding(model_name=MODEL_NAME)
            q = np.asarray(next(iter(model.embed([query]))), dtype=np.float32)

            norms = np.linalg.norm(matrix, axis=1) + 1e-9
            qnorm = np.linalg.norm(q) + 1e-9
            sims = (matrix @ q) / (norms * qnorm)

            idx = np.argsort(sims)[::-1][:limit]
            return [(paths[i], float(sims[i])) for i in idx if sims[i] > 0.0]
        except Exception:  # noqa: BLE001
            return []

    def status(self) -> dict:
        return {
            "available": self.is_available(),
            "model_cached": self.model_cached(),
            "has_index": self.has_index(),
            "index_dir": str(self.dir),
        }
