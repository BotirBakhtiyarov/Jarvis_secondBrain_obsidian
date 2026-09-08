"""Semantik (vektor) qidiruv — optional.

`fastembed` o'rnatilgan bo'lsa ishlaydi (ONNX asosida, torch'siz). Indeks
`reindex` tool orqali quriladi va `.jarvis_index/` papkasida saqlanadi.
Qidiruv faqat mavjud indeks bilan ishlaydi — hech qachon o'z-o'zidan model
yuklab olmaydi (osilib qolishning oldini olish uchun).
"""

import json
from pathlib import Path

MODEL_NAME = "BAAI/bge-small-en-v1.5"
INDEX_DIR = ".jarvis_index"


class SemanticIndex:
    def __init__(self, vault_root: Path):
        self.root = Path(vault_root)
        self.dir = self.root / INDEX_DIR

    @staticmethod
    def is_available() -> bool:
        try:
            import fastembed  # noqa: F401
            return True
        except Exception:  # noqa: BLE001
            return False

    def _mark_disabled(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "disabled").touch()

    def _is_disabled(self) -> bool:
        return (self.dir / "disabled").exists()

    def has_index(self) -> bool:
        return (
            not self._is_disabled()
            and (self.dir / "vectors.npy").exists()
            and (self.dir / "paths.json").exists()
        )

    def build(self, notes: list[tuple[str, str]]) -> None:
        """Indeksni quradi (model yuklab olinishi mumkin — uzun)."""

        import numpy as np
        from fastembed import TextEmbedding

        model = TextEmbedding(model_name=MODEL_NAME)
        paths = [p for p, _ in notes]
        texts = [c[:4000] for _, c in notes]

        vectors = [np.asarray(emb, dtype=np.float32) for emb in model.embed(texts)]
        matrix = np.vstack(vectors) if vectors else np.zeros((0, 1), dtype=np.float32)

        self.dir.mkdir(parents=True, exist_ok=True)
        np.save(self.dir / "vectors.npy", matrix)
        (self.dir / "paths.json").write_text(
            json.dumps(paths, ensure_ascii=False), encoding="utf-8"
        )
        (self.dir / "disabled").unlink(missing_ok=True)

    def search(self, query: str, limit: int = 10) -> list[tuple[str, float]]:
        """Mavjud indeks bo'yicha qidiruv; indeks bo'lmasa [] qaytaradi."""

        import numpy as np
        from fastembed import TextEmbedding

        if not self.has_index():
            return []

        try:
            matrix = np.load(self.dir / "vectors.npy")
            paths = json.loads((self.dir / "paths.json").read_text(encoding="utf-8"))

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
