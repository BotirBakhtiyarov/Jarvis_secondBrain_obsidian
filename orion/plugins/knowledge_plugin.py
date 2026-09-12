"""Unified knowledge search across workspace code and Obsidian notes.

Combines keyword search (always available) with optional semantic vector
search (when fastembed is installed and an index has been built).
"""

from pathlib import Path

from orion.tools import Tool


def register(registry, config):
    registry.register(SearchKnowledgeTool(config))


class SearchKnowledgeTool(Tool):
    """Search the user's projects and notes in one call.

    Returns ranked results from both the workspace (code files) and the
    Obsidian vault (Markdown notes), blending keyword and semantic matches.
    """

    def __init__(self, config):
        super().__init__(
            name="search_knowledge",
            description=(
                "Search the user's workspace code and Obsidian notes together. "
                "Returns ranked results with path, score and a relevant excerpt. "
                "Use this whenever you need to find information that could be in "
                "either the project files or the user's notes/knowledge base."
            ),
            parameters={
                "query": {
                    "type": "string",
                    "description": "What to search for (natural language).",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 10).",
                },
            },
            required=["query"],
        )
        self.config = config

    def execute(self, query, limit=10):
        from orion.obsidian import open_vault
        from orion.semantic import SemanticIndex

        limit = max(1, min(int(limit or 10), 30))
        vault = open_vault(self.config)

        # --- Obsidian notes (keyword + semantic) ---
        note_results = vault.search(query, limit=limit)

        # --- Workspace code (keyword + semantic when index exists) ---
        code_results = self._search_workspace(query, limit=limit)

        # --- Merge, dedupe by path, keep highest score ---
        merged: dict[str, dict] = {}
        for r in note_results:
            merged[r["path"]] = {
                "path": r["path"],
                "source": "notes",
                "score": r["score"],
                "excerpt": r.get("excerpt", ""),
            }
        for r in code_results:
            path = r["path"]
            if path in merged:
                merged[path]["score"] += r["score"]
                merged[path]["source"] = "notes+code"
            else:
                merged[path] = {
                    "path": path,
                    "source": "code",
                    "score": r["score"],
                    "excerpt": r.get("excerpt", ""),
                }

        out = sorted(merged.values(), key=lambda x: x["score"], reverse=True)

        # --- Semantic search over combined index (notes + code) when available ---
        semantic = SemanticIndex(vault.root)
        semantic_results = semantic.search(query, limit=limit)
        if semantic_results and semantic.is_available() and semantic.has_index():
            # Inject semantic matches, boosting their score
            for path, sim in semantic_results:
                if path in merged:
                    merged[path]["score"] += sim * 2.0
                    merged[path]["source"] = merged[path].get("source", "notes") + "+semantic"
                else:
                    merged[path] = {
                        "path": path,
                        "source": "semantic",
                        "score": sim * 2.0,
                        "excerpt": "",
                    }

        out = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
        return {
            "query": query,
            "results": out[:limit],
            "semantic_available": semantic.is_available() and semantic.has_index(),
        }

    def _search_workspace(self, query: str, limit: int) -> list[dict]:
        """Keyword search over workspace files (code, markdown, text)."""

        import re

        root = Path(self.config.workspace)
        if not root.exists():
            return []

        query_lower = query.lower().strip()
        words = [w for w in re.findall(r"[a-z0-9_']+", query_lower) if len(w) >= 3]
        results: list[dict] = []

        skip_dirs = {".git", ".venv", "venv", "node_modules", "__pycache__", "dist", "build"}
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if any(part in skip_dirs for part in path.parts):
                continue
            if path.suffix not in _CODE_SUFFIXES:
                continue

            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            lower = content.lower()
            score = 0
            if query_lower and query_lower in lower:
                score += 15
            for word in words:
                score += min(lower.count(word), 6)

            if score > 0:
                excerpt = self._excerpt(lower, words or [query_lower])
                results.append(
                    {
                        "path": str(path.relative_to(root)),
                        "score": float(score),
                        "excerpt": excerpt,
                    }
                )

        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:limit]

    @staticmethod
    def _excerpt(content_lower: str, words: list[str]) -> str:
        """Pull a short snippet around the first keyword match."""
        import re

        if not words:
            return ""
        pos = -1
        for w in words:
            pos = content_lower.find(w)
            if pos != -1:
                break
        if pos == -1:
            return ""
        start = max(0, pos - 60)
        end = min(len(content_lower), pos + 120)
        snippet = content_lower[start:end].strip()
        snippet = re.sub(r"\s+", " ", snippet)
        return ("..." if start else "") + snippet + ("..." if end < len(content_lower) else "")


_CODE_SUFFIXES = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".go",
    ".rs",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".rb",
    ".php",
    ".swift",
    ".kt",
    ".kts",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".cfg",
    ".ini",
    ".sh",
    ".sql",
    ".css",
    ".html",
    ".xml",
}
