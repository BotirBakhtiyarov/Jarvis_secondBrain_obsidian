"""Semantik (vektor) qidiruv — optional.

`fastembed` o'rnatilgan bo'lsa ishlaydi (ONNX asosida, torch'siz). Indeks
`reindex` tool orqali quriladi va `.orion_index/` papkasida saqlanadi.

Qidiruv faqat (1) mavjud indeks va (2) mahalliy cache'da mavjud model bilan
ishlaydi — hech qachon o'z-o'zidan model yuklab olmaydi. Model faqat `reindex`
paytida yuklab olinadi, bu esa osilib qolish (tarmoq kutilishi) xatosini
bartaraf etadi.
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
        """Embedding modeli mahalliy cache'da mavjudmi — tarmoqsiz tekshiruv.

        fastembed modellarni `~/.cache/fastembed/` (yoki `FASTEMBED_CACHE_PATH`)
        ichiga saqlaydi. U yerda model papkasi bo'lmasa, qidiruv modelni
        yuklab olmaydi — aks holda tarmoq bo'lmaganda osilib qoladi.
        """

        cache = Path(
            os.environ.get(
                "FASTEMBED_CACHE_PATH",
                Path.home() / ".cache" / "fastembed",
            )
        )
        if not cache.exists():
            return False

        stem = MODEL_NAME.replace("/", "__")
        return (cache / stem).exists() or any(
            p.is_dir() for p in cache.iterdir() if stem in p.name
        )

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

    def build(self, notes: list[tuple[str, str]], progress=None) -> None:
        """Indeksni quradi (model birinchi marta yuklab olinishi mumkin).

        `progress(done, total)` callback'i (ixtiyoriy) UI progress-bar uchun.
        """

        import numpy as np
        from fastembed import TextEmbedding

        model = TextEmbedding(model_name=MODEL_NAME)
        paths = [p for p, _ in notes]
        texts = [c[:4000] for _, c in notes]

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
        """Mavjud indeks va cache'dagi model bo'yicha qidiruv.

        Indeks yoki model cache'da bo'lmasa `[]` qaytaradi — hech qachon
        tarmoqdan model yuklab olmaydi.
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
        """UI/status uchun indeks holati."""

        return {
            "available": self.is_available(),
            "model_cached": self.model_cached(),
            "has_index": self.has_index(),
            "index_dir": str(self.dir),
        }
