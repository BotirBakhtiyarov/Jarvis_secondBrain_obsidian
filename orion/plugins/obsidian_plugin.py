from orion.obsidian import Vault, open_vault
from orion.tools import Tool


def register(registry, config):
    vault = open_vault(config)
    registry.register(SearchNotesTool(vault))
    registry.register(ReadNoteTool(vault))
    registry.register(CreateNoteTool(vault))
    registry.register(UpdateNoteTool(vault))
    registry.register(AppendNoteTool(vault))
    registry.register(ListNotesTool(vault))
    registry.register(LinkNotesTool(vault))


class SearchNotesTool(Tool):
    def __init__(self, vault: Vault):
        super().__init__(
            name="search_notes",
            description=(
                "Search the user's Obsidian Second Brain. Returns ranked "
                "results with a relevant excerpt. Use this before creating "
                "or updating notes to avoid duplicates, and whenever you "
                "need information from the user's notes, ideas, plans or "
                "knowledge."
            ),
            parameters={
                "query": {
                    "type": "string",
                    "description": "What to search for",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 10)",
                },
            },
            required=["query"],
        )
        self.vault = vault

    def execute(self, query, limit=10):
        out = {"results": self.vault.search(query, limit)}
        try:
            from orion.semantic import SemanticIndex

            status = SemanticIndex(self.vault.root).status()
            if status["available"] and not status["has_index"]:
                out["hint"] = (
                    "Semantic index not built yet — run the `reindex` tool once "
                    "to enable semantic search."
                )
        except Exception:  # noqa: BLE001
            pass
        return out


class ReadNoteTool(Tool):
    def __init__(self, vault: Vault):
        super().__init__(
            name="read_note",
            description="Read the complete content of an Obsidian note.",
            parameters={
                "note_path": {
                    "type": "string",
                    "description": "Relative path of the note inside the vault",
                }
            },
            required=["note_path"],
        )
        self.vault = vault

    def execute(self, note_path):
        return self.vault.read(note_path)


class CreateNoteTool(Tool):
    def __init__(self, vault: Vault):
        super().__init__(
            name="create_note",
            description=(
                "Create a new note in the Obsidian Vault. Use only when no "
                "suitable existing note exists (search first)."
            ),
            parameters={
                "note_path": {
                    "type": "string",
                    "description": "Relative path, e.g. Inbox/New Idea.md",
                },
                "content": {
                    "type": "string",
                    "description": "Markdown content of the note",
                },
            },
            required=["note_path", "content"],
        )
        self.vault = vault

    def execute(self, note_path, content):
        return self.vault.create(note_path, content)


class UpdateNoteTool(Tool):
    def __init__(self, vault: Vault):
        super().__init__(
            name="update_note",
            description=(
                "Update an existing note. Read it first, then provide the "
                "complete updated Markdown content. A backup is made "
                "automatically. Do not create a duplicate note if relevant "
                "information already exists."
            ),
            parameters={
                "note_path": {"type": "string", "description": "Existing note path"},
                "content": {
                    "type": "string",
                    "description": "Complete updated Markdown content",
                },
            },
            required=["note_path", "content"],
        )
        self.vault = vault

    def execute(self, note_path, content):
        return self.vault.update(note_path, content)


class AppendNoteTool(Tool):
    def __init__(self, vault: Vault):
        super().__init__(
            name="append_to_note",
            description=(
                "Append information to an existing note without replacing "
                "its content. Use when adding new information while "
                "preserving the current note."
            ),
            parameters={
                "note_path": {"type": "string"},
                "content": {"type": "string"},
            },
            required=["note_path", "content"],
        )
        self.vault = vault

    def execute(self, note_path, content):
        return self.vault.append(note_path, content)


class ListNotesTool(Tool):
    def __init__(self, vault: Vault):
        super().__init__(
            name="list_notes",
            description=(
                "List available Obsidian notes. Use to understand the "
                "structure of the user's Second Brain."
            ),
            parameters={
                "folder": {
                    "type": "string",
                    "description": "Optional folder path",
                }
            },
        )
        self.vault = vault

    def execute(self, folder=""):
        return self.vault.list_notes(folder)


class LinkNotesTool(Tool):
    def __init__(self, vault: Vault):
        super().__init__(
            name="link_notes",
            description=(
                "Add two-way [[wikilinks]] between notes. Provide the source "
                "note and the related target notes; each target gets a "
                "`## Backlinks` section linking back to the source. "
                "Deduplicated automatically — existing links are skipped."
            ),
            parameters={
                "source_path": {
                    "type": "string",
                    "description": "The note that contains the outgoing links",
                },
                "target_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Related note paths to backlink to the source",
                },
            },
            required=["source_path", "target_paths"],
        )
        self.vault = vault

    def execute(self, source_path, target_paths):
        added = self.vault.add_backlinks(source_path, target_paths)
        return {
            "success": True,
            "action": "linked",
            "source": source_path,
            "backlinks": added,
        }
