import subprocess

from orion.tools import Tool
from orion.workspace import Workspace


def register(registry, config):
    ws = Workspace(config.workspace)
    registry.register(ListFilesTool(ws))
    registry.register(ReadFileTool(ws))
    registry.register(WriteFileTool(ws))
    registry.register(EditFileTool(ws))
    registry.register(RunCommandTool(ws))


def _truncate(text: str, limit: int = 4000) -> str:
    if text and len(text) > limit:
        return text[:limit] + "\n… [truncated]"
    return text


class ListFilesTool(Tool):
    def __init__(self, ws: Workspace):
        super().__init__(
            name="list_files",
            description=(
                "List files and folders inside the workspace (or a subfolder). "
                "Use to explore the user's projects."
            ),
            parameters={
                "folder": {
                    "type": "string",
                    "description": "Folder relative to workspace root (empty = root)",
                }
            },
        )
        self.ws = ws

    def execute(self, folder=""):
        return self.ws.list_files(folder)


class ReadFileTool(Tool):
    def __init__(self, ws: Workspace):
        super().__init__(
            name="read_file",
            description=(
                "Read a file from the workspace. Use start/end to read a "
                "specific line range of large files."
            ),
            parameters={
                "path": {"type": "string", "description": "File path relative to workspace"},
                "start": {"type": "integer", "description": "Start line (default 1)"},
                "end": {"type": "integer", "description": "End line (optional)"},
            },
            required=["path"],
        )
        self.ws = ws

    def execute(self, path, start=1, end=None):
        return self.ws.read_file(path, start=start, end=end)


class WriteFileTool(Tool):
    def __init__(self, ws: Workspace):
        super().__init__(
            name="write_file",
            description=(
                "Create a new file or overwrite an existing one in the "
                "workspace. Creates parent folders automatically."
            ),
            parameters={
                "path": {"type": "string", "description": "File path relative to workspace"},
                "content": {"type": "string", "description": "Full file content"},
            },
            required=["path", "content"],
        )
        self.ws = ws

    def execute(self, path, content):
        return self.ws.write_file(path, content)


class EditFileTool(Tool):
    def __init__(self, ws: Workspace):
        super().__init__(
            name="edit_file",
            description=(
                "Edit a file by replacing an exact text snippet. Provide a "
                "unique old_text and the new_text. If the snippet appears "
                "multiple times, add more surrounding context to make it "
                "unique. Verify with read_file afterward."
            ),
            parameters={
                "path": {"type": "string", "description": "File path relative to workspace"},
                "old_text": {"type": "string", "description": "Exact existing text to replace"},
                "new_text": {"type": "string", "description": "Replacement text"},
            },
            required=["path", "old_text", "new_text"],
        )
        self.ws = ws

    def execute(self, path, old_text, new_text):
        return self.ws.edit_file(path, old_text, new_text)


class RunCommandTool(Tool):
    def __init__(self, ws: Workspace):
        super().__init__(
            name="run_command",
            description=(
                "Run a shell command inside the workspace and return its "
                "output. Use for running tests, builds, git status, "
                "installing dependencies, or any command needed to inspect "
                "or work on the user's projects.\n\n"
                "SAFETY: Never run destructive or irreversible commands "
                "(rm -rf, git push --force, git reset --hard, deleting "
                "data/branches, dropping tables) without the user's "
                "explicit confirmation. Prefer read-only commands first."
            ),
            parameters={
                "command": {
                    "type": "string",
                    "description": "Shell command to run",
                }
            },
            required=["command"],
        )
        self.ws = ws

    def execute(self, command, timeout=60):
        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.ws.root),
            )
        except subprocess.TimeoutExpired:
            return {"error": f"Command timed out after {timeout}s"}
        except Exception as err:  # noqa: BLE001
            return {"error": f"{type(err).__name__}: {err}"}

        return {
            "exit_code": proc.returncode,
            "stdout": _truncate(proc.stdout),
            "stderr": _truncate(proc.stderr),
        }
