from datetime import datetime
from pathlib import Path

from jarvis.obsidian import Vault
from jarvis.tools import Tool

_INVALID_CHARS = set('/\\:*?"<>|')


def register(registry, config):
    vault = Vault(config.obsidian_vault)
    registry.register(SaveMemoryTool(vault))


class SaveMemoryTool(Tool):
    def __init__(self, vault: Vault):
        super().__init__(
            name="save_memory",
            description=(
                "Store a piece of information in the user's Obsidian Second "
                "Brain (long-term memory).\n\n"
                "SAVE when the message contains: an explicit request "
                "('remember this', 'save this', 'note this'), stable facts "
                "about the user (preferences, personal details, goals, "
                "plans, decisions), project facts not already in the files, "
                "new ideas, tasks/todos, or things the user learned.\n\n"
                "DO NOT save: small talk, greetings, transient questions, "
                "code that already lives in files, one-off queries with no "
                "lasting value.\n\n"
                "When unsure, ask the user. Never store secrets (passwords, "
                "API keys, tokens)."
            ),
            parameters={
                "title": {
                    "type": "string",
                    "description": "Short note title, e.g. 'Project X decisions'",
                },
                "content": {
                    "type": "string",
                    "description": "Markdown content to store",
                },
                "folder": {
                    "type": "string",
                    "description": "Folder inside the vault (default 'Inbox')",
                },
            },
            required=["title", "content"],
        )
        self.vault = vault

    def execute(self, title, content, folder="Inbox"):
        safe_title = "".join(c for c in title.strip() if c not in _INVALID_CHARS)
        safe_title = safe_title.strip() or "Note"

        folder = (folder or "Inbox").strip("/")
        note_path = f"{folder}/{safe_title}.md" if folder else f"{safe_title}.md"

        path = self.vault.safe_path(note_path)
        if path.exists():
            return self.vault.append(note_path, self._dated(content))

        # Xuddi shu sarlavhali mavjud nota bormi — dublikat oldini olish
        results = self.vault.search(safe_title, limit=3)
        for res in results:
            stem = res["path"].rsplit("/", 1)[-1].removesuffix(".md").lower()
            if stem == safe_title.lower():
                return self.vault.append(res["path"], self._dated(content))

        # Yangi nota: frontmatter + kontent + bog'langan notalar
        tags = [t.strip().lower() for t in folder.split("/") if t.strip()]
        related = self.vault.find_related(safe_title, limit=5, exclude=note_path)

        body = self.vault.build_frontmatter(safe_title, tags)
        body += content.strip() + "\n"

        if related:
            body += "\n## Related\n"
            for rel in related:
                body += f"- {self.vault.note_link(rel)}\n"

        return self.vault.create(note_path, body)

    def _dated(self, content: str) -> str:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        return f"## {stamp}\n\n{content.strip()}"
