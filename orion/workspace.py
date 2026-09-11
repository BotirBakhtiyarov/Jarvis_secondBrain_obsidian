from pathlib import Path

MAX_READ_CHARS = 20000
MAX_LIST_ENTRIES = 300


class Workspace:
    """Loyiha fayllari ustidagi xavfsiz amallar.

    Barcha yo'llar `root` ichida bo'lishi shart — tashqariga chiqish
    bloklanadi (path traversal himoyasi).
    """

    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()

    def safe_path(self, rel: str) -> Path:
        path = (self.root / rel).resolve()
        if self.root not in path.parents and path != self.root:
            raise ValueError("Path is outside the workspace")
        return path

    def list_files(self, folder: str = "", max_entries: int = MAX_LIST_ENTRIES) -> dict:
        base = self.safe_path(folder) if folder else self.root

        if not base.exists():
            return {"error": "Folder not found", "folder": folder}

        entries = []
        for p in sorted(base.iterdir()):
            entries.append(
                {
                    "name": p.name,
                    "path": str(p.relative_to(self.root)) if p != self.root else ".",
                    "type": "dir" if p.is_dir() else "file",
                }
            )

        total = len(entries)
        return {
            "folder": folder or ".",
            "entries": entries[:max_entries],
            "total": total,
            "truncated": total > max_entries,
        }

    def read_file(
        self,
        path: str,
        start: int = 1,
        end: int | None = None,
    ) -> dict:
        p = self.safe_path(path)

        if not p.exists():
            return {"error": "File not found", "path": path}
        if p.is_dir():
            return {
                "error": "Path is a directory, not a file. Use list_files",
                "path": path,
            }

        content = p.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()
        total = len(lines)

        start = max(1, start)
        end = end if end is not None else total

        selected = lines[start - 1 : end]
        text = "\n".join(selected)

        truncated = len(text) > MAX_READ_CHARS
        if truncated:
            text = text[:MAX_READ_CHARS]

        return {
            "path": path,
            "start_line": start,
            "end_line": start + len(selected) - 1 if selected else start,
            "total_lines": total,
            "content": text,
            "truncated": truncated,
        }

    def write_file(self, path: str, content: str) -> dict:
        p = self.safe_path(path)
        existed = p.exists()

        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

        return {
            "success": True,
            "action": "updated" if existed else "created",
            "path": path,
        }

    def edit_file(
        self,
        path: str,
        old_text: str,
        new_text: str,
        replace_all: bool = False,
    ) -> dict:
        p = self.safe_path(path)

        if not p.exists():
            return {"error": "File not found", "path": path}

        content = p.read_text(encoding="utf-8", errors="ignore")
        count = content.count(old_text)

        if count == 0:
            return {"error": "old_text not found in file", "path": path}

        if not replace_all and count > 1:
            return {
                "error": (f"old_text appears {count} times. Provide more (unique) context"),
                "path": path,
            }

        p.write_text(content.replace(old_text, new_text), encoding="utf-8")

        return {
            "success": True,
            "action": "edited",
            "path": path,
            "replacements": count,
        }
