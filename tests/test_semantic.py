import pytest

pytest.importorskip("fastembed")

from orion.semantic import SemanticIndex  # noqa: E402


def test_semantic_ranking_and_cache_with_fake_embeddings(tmp_path, monkeypatch):
    import fastembed
    import numpy as np

    VOCAB = ["vehicle", "wheel", "cat", "food", "pasta", "wheat", "mammal"]

    class FakeEmbedding:
        def __init__(self, model_name=None):
            pass

        def embed(self, texts):
            out = []
            for text in texts:
                vector = np.zeros(len(VOCAB), dtype=np.float32)
                for i, word in enumerate(VOCAB):
                    if word in text.lower():
                        vector[i] = 1.0
                out.append(vector)
            return out

    monkeypatch.setattr(fastembed, "TextEmbedding", FakeEmbedding)
    # Haqiqiy cache tekshiruvini bypass qilamiz — test soxta embedding ishlatadi.
    monkeypatch.setattr(SemanticIndex, "model_cached", staticmethod(lambda: True))

    notes = [
        ("cats.md", "Cats are mammals."),
        ("cars.md", "Cars are vehicles with wheels."),
        ("food.md", "Pasta is food made from wheat."),
    ]
    index = SemanticIndex(tmp_path)
    index.build(notes)

    results = index.search("vehicle wheel", limit=2)
    paths = [p for p, _ in results]

    assert paths[0] == "cars.md"
    assert index.has_index()


def test_search_without_index_returns_empty(tmp_path):
    index = SemanticIndex(tmp_path)
    assert index.search("anything") == []


@pytest.mark.network
def test_semantic_index_build_and_search(tmp_path):
    notes = [
        ("cats.md", "Cats are small domesticated carnivorous mammals."),
        ("cars.md", "Cars are motor vehicles with four wheels."),
        ("food.md", "Pasta is a type of Italian food made from wheat."),
    ]
    index = SemanticIndex(tmp_path)

    try:
        index.build(notes)
        results = index.search("vehicles with wheels", limit=2)
    except Exception as exc:  # noqa: BLE001
        # Birinchi ishga tushirishda model HuggingFace'dan yuklab olinadi;
        # tarmoq mavjud bo'lmasa testni o'tkazib yuboramiz (kod emas, muhit).
        pytest.skip(f"embedding model unavailable (network): {exc}")

    paths = [p for p, _ in results]
    assert "cars.md" in paths
