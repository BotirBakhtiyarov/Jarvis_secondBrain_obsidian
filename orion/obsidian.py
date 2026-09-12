import re
from datetime import datetime
from pathlib import Path

from orion.obsidian_transport import IGNORED_DIRS, FileTransport, make_transport

MAX_READ_CHARS = 30000
MAX_EXCERPT_CHARS = 1500

__all__ = ["IGNORED_DIRS", "Vault", "open_vault"]


class Vault:
    """All operations on an Obsidian vault.

    The vault root is injectable for tests, and writes go through a *transport*
    (local filesystem by default, or the Obsidian Local REST API). See
    :mod:`orion.obsidian_transport`.
    """

    def __init__(self, root: Path, transport=None):
        self.root = Path(root).expanduser().resolve()
        self.transport = transport or FileTransport(self.root)

    # Helpers

    def safe_path(self, note_path: str) -> Path:
        """Resolve a path inside the vault, blocking path traversal."""

        path = (self.root / note_path).resolve()
        if self.root not in path.parents and path != self.root:
            raise ValueError("Invalid note path (outside the vault)")
        return path

    def _rel(self, note: Path | str) -> str:
        """Vault-relative, forward-slash path for the transport."""

        return Path(note).relative_to(self.root).as_posix()

    def get_all_notes(self) -> list[Path]:
        return [self.root / rel for rel in self.transport.list_markdown()]

    def iter_notes(self) -> list[tuple[str, str]]:
        """Return all notes as (path, content) pairs."""

        out = []
        for note in self.get_all_notes():
            try:
                out.append((self._rel(note), self._read(note)))
            except OSError:
                continue
        return out

    def _read(self, note: Path) -> str:
        return self.transport.read(self._rel(note))

    def _frontmatter(self, content: str) -> dict:
        """Parse YAML frontmatter simply (no external YAML dependency)."""

        if not content.startswith("---"):
            return {}

        end = content.find("\n---", 3)
        if end == -1:
            return {}

        data: dict = {}
        for line in content[3:end].splitlines():
            line = line.strip()
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip().lower()
            value = value.strip().strip('"').strip("'")
            if key in ("tags", "tag"):
                data[key] = [
                    t.strip()
                    for t in value.replace("[", "").replace("]", "").split(",")
                    if t.strip()
                ]
            else:
                data[key] = value
        return data

    def _frontmatter_tags(self, content: str) -> list[str]:
        fm = self._frontmatter(content)
        tags = fm.get("tags", [])
        return tags if isinstance(tags, list) else [str(tags)]

    def _best_excerpt(
        self,
        content: str,
        query_lower: str,
        words: list[str],
        max_chars: int = MAX_EXCERPT_CHARS,
    ) -> str:
        """Best-matching excerpt inside a note (for RAG)."""

        blocks = re.split(r"\n\s*\n", content)
        if not blocks:
            return ""

        best = ""
        best_score = -1

        for block in blocks:
            lower = block.lower()
            score = 0
            if query_lower and query_lower in lower:
                score += 5
            for word in words:
                score += min(lower.count(word), 3)
            if score > best_score:
                best_score = score
                best = block

        if not best:
            best = content

        best = best.strip()
        if len(best) > max_chars:
            best = best[:max_chars] + "\n…"
        return best

    # Search

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Hybrid search: keyword + semantic (when an index exists)."""

        keyword = self._keyword_search(query, limit=limit * 3)

        semantic: dict[str, float] = {}
        try:
            from orion.semantic import SemanticIndex

            index = SemanticIndex(self.root)
            if index.has_index():
                for path, sim in index.search(query, limit=limit * 3):
                    if sim > 0.0:
                        semantic[path] = sim
        except Exception:  # noqa: BLE001
            semantic = {}

        merged: dict[str, dict] = {}
        for r in keyword:
            merged[r["path"]] = {"score": r["score"], "excerpt": r["excerpt"]}

        max_kw = max((r["score"] for r in keyword), default=1.0)
        for path, sim in semantic.items():
            bonus = sim * max(10.0, max_kw * 0.5)
            if path in merged:
                merged[path]["score"] += bonus
            else:
                merged[path] = {"score": bonus, "excerpt": ""}

        out = [
            {"path": p, "score": round(v["score"], 1), "excerpt": v["excerpt"]}
            for p, v in merged.items()
        ]
        out.sort(key=lambda r: r["score"], reverse=True)
        return out[:limit]

    def _keyword_search(self, query: str, limit: int = 10) -> list[dict]:
        """Ranked search by note name, tags and content."""

        query_lower = query.lower().strip()
        words = [w for w in re.findall(r"[a-z0-9_']+", query_lower) if len(w) >= 3]

        results: list[dict] = []

        for note in self.get_all_notes():
            try:
                content = self._read(note)
            except OSError:
                continue

            lower = content.lower()
            name_lower = note.name.lower()
            stem_lower = note.stem.lower()

            score = 0

            if query_lower:
                if query_lower in name_lower:
                    score += 30
                if query_lower in stem_lower:
                    score += 20
                if query_lower in lower:
                    score += 15

            for word in words:
                if word in name_lower:
                    score += 8
                if word in stem_lower:
                    score += 5
                score += min(lower.count(word), 6)

            for tag in self._frontmatter_tags(content):
                tag_lower = tag.lower()
                if query_lower and query_lower in tag_lower:
                    score += 10
                for word in words:
                    if word in tag_lower:
                        score += 3

            if score <= 0:
                continue

            results.append(
                {
                    "path": self._rel(note),
                    "score": score,
                    "excerpt": self._best_excerpt(content, query_lower, words),
                }
            )

        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:limit]

    # CRUD

    def read(self, note_path: str) -> dict:
        self.safe_path(note_path)
        if not self.transport.exists(note_path):
            return {"error": "Note not found", "path": note_path}

        content = self.transport.read(note_path)
        truncated = len(content) > MAX_READ_CHARS
        if truncated:
            content = content[:MAX_READ_CHARS]

        return {
            "path": note_path,
            "content": content,
            "truncated": truncated,
        }

    def create(self, note_path: str, content: str) -> dict:
        self.safe_path(note_path)

        if self.transport.exists(note_path):
            return {
                "success": False,
                "error": "Note already exists",
                "path": note_path,
            }

        self.transport.write(note_path, content)

        return {"success": True, "action": "created", "path": note_path}

    def update(self, note_path: str, content: str) -> dict:
        self.safe_path(note_path)

        if not self.transport.exists(note_path):
            return {
                "success": False,
                "error": "Note not found",
                "path": note_path,
            }

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_rel = f".orion_backups/{Path(note_path).stem}_{timestamp}.md"
        old_content = self.transport.read(note_path)
        self.transport.write(backup_rel, old_content)
        self.transport.write(note_path, content)

        return {
            "success": True,
            "action": "updated",
            "path": note_path,
            "backup": backup_rel,
        }

    def append(self, note_path: str, content: str) -> dict:
        self.safe_path(note_path)

        if not self.transport.exists(note_path):
            return {
                "success": False,
                "error": "Note not found",
                "path": note_path,
            }

        self.transport.append(note_path, "\n\n" + content)

        return {"success": True, "action": "appended", "path": note_path}

    def move(self, note_path: str, new_path: str) -> dict:
        """Move a note to another folder (Inbox triage)."""

        self.safe_path(note_path)
        self.safe_path(new_path)
        if not self.transport.exists(note_path):
            return {"success": False, "error": "Note not found", "path": note_path}

        if self.transport.exists(new_path):
            return {
                "success": False,
                "error": "Target already exists",
                "path": new_path,
            }

        self.transport.move(note_path, new_path)
        return {"success": True, "action": "moved", "from": note_path, "to": new_path}

    def list_notes(self, folder: str = "", limit: int = 500) -> dict:
        if folder:
            self.safe_path(folder)

        notes = self.transport.list_markdown(folder.rstrip("/"))
        total = len(notes)

        return {
            "folder": folder or ".",
            "total": total,
            "notes": notes[:limit],
            "truncated": total > limit,
        }

    # Note design helpers (frontmatter + wikilinks)

    def build_frontmatter(self, title: str, tags: list[str] | None = None) -> str:
        """Build Obsidian YAML frontmatter (created date + tags)."""

        created = datetime.now().strftime("%Y-%m-%d")
        lines = ["---", f'title: "{title}"', f"created: {created}"]
        if tags:
            lines.append("tags: [" + ", ".join(tags) + "]")
        lines.append("---")
        return "\n".join(lines) + "\n\n"

    def note_link(self, note_path: str) -> str:
        """Obsidian wikilink — `[[Note Name]]`."""

        return f"[[{Path(note_path).stem}]]"

    def find_related(self, query: str, limit: int = 5, exclude: str = "") -> list[str]:
        """Return paths of existing notes matching the query."""

        results = self.search(query, limit=limit)
        return [r["path"] for r in results if r["path"] != exclude]

    def add_backlinks(self, source_path: str, target_paths: list[str]) -> list[str]:
        """Add a backlink to each target note for the source note.

        Two-way linking: if the source links ``[[Target]]``, the target gets
        a ``## Backlinks`` section with ``[[Source]]``. Idempotent.
        """

        source_stem = Path(source_path).stem
        link = f"[[{source_stem}]]"
        added: list[str] = []

        for target in target_paths:
            if not target or target == source_path:
                continue
            try:
                self.safe_path(target)
            except ValueError:
                continue
            if not self.transport.exists(target):
                continue

            content = self.transport.read(target)
            if link in content:
                continue

            if "## Backlinks" in content:
                new_content = content.replace("## Backlinks", f"## Backlinks\n- {link}", 1)
            else:
                new_content = content.rstrip() + f"\n\n## Backlinks\n- {link}\n"

            self.transport.write(target, new_content)
            added.append(target)

        return added


def open_vault(config) -> Vault:
    """Build a :class:`Vault` using the transport from ``config``."""
    return Vault(config.obsidian_vault, transport=make_transport(config))
