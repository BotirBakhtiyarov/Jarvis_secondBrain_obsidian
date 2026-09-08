import pytest

pytest.importorskip("fastembed")

from jarvis.semantic import SemanticIndex  # noqa: E402


def test_semantic_index_build_and_search(tmp_path):
    notes = [
        ("cats.md", "Cats are small domesticated carnivorous mammals."),
        ("cars.md", "Cars are motor vehicles with four wheels."),
        ("food.md", "Pasta is a type of Italian food made from wheat."),
    ]
    index = SemanticIndex(tmp_path)

    results = index.search(notes, "vehicles with wheels", limit=2)
    paths = [p for p, _ in results]

    assert "cars.md" in paths
