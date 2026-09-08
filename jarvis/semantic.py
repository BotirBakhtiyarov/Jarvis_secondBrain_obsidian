"""Semantik (vektor) qidiruv — optional.

`fastembed` o'rnatilgan bo'lsa ishlaydi (ONNX asosida, torch'siz). U yo'q
bo'lsa `Vault.search` oddiy keyword qidiruvga tushib qoladi. Indeks
`.jarvis_index/` papkasida saqlanadi va notalar o'zgarsa avtomatik
qayta quriladi.
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

    def _fingerprint(self, notes: list[tuple[str, str]]) -> str:
        import hashlib

        h = hashlib.md5()
        for path, content in notes:
            h.update(str(path).encode("utf-8"))
            h.update(str(len(content)).encode("utf-8"))
            h.update(content[:256].encode("utf-8", "ignore"))
        return h.hexdigest()

    def build(self, notes: list[tuple[str, str]]) -> None:
        import numpy as np
        from fastembed import TextEmbedding

        model = TextEmbedding(model_name=MODEL_NAME)
        paths = [p for p, _ in notes]
        texts = [c[:4000] for _, c in notes]

        vectors = [np.asarray(emb, dtype=np.float32) for emb in model.embed(texts)]
        if not vectors:
            matrix = np.zeros((0, 1), dtype=np.float32)
        else:
            matrix = np.vstack(vectors)

        self.dir.mkdir(parents=True, exist_ok=True)
        np.save(self.dir / "vectors.npy", matrix)
        (self.dir / "paths.json").write_text(
            json.dumps(paths, ensure_ascii=False), encoding="utf-8"
        )
        (self.dir / "fingerprint.json").write_text(
            json.dumps({"fp": self._fingerprint(notes)}), encoding="utf-8"
        )

    def _is_fresh(self, notes: list[tuple[str, str]]) -> bool:
        fp_file = self.dir / "fingerprint.json"
        if not fp_file.exists():
            return False
        try:
            return (
                json.loads(fp_file.read_text(encoding="utf-8")).get("fp")
                == self._fingerprint(notes)
            )
        except Exception:  # noqa: BLE001
            return False

    def search(
        self,
        notes: list[tuple[str, str]],
        query: str,
        limit: int = 10,
    ) -> list[tuple[str, float]]:
        """notes: [(relative_path, content)]; natija: [(path, o'xshashlik)]."""

        import numpy as np
        from fastembed import TextEmbedding

        if not self._is_fresh(notes):
            self.build(notes)

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
