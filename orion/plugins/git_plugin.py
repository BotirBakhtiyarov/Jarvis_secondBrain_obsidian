"""Git integration: status/diff/log (read-only) and commit/PR (write).

Write tools (``git_commit``, ``git_create_pr``) are permission-gated.
"""

import subprocess

from orion.tools import Tool


def _run(ws, *args, timeout=30):
    try:
        proc = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(ws),
        )
    except FileNotFoundError:
        return {"error": "git is not installed or not on PATH"}
    except subprocess.TimeoutExpired:
        return {"error": f"git command timed out after {timeout}s"}

    return {
        "exit_code": proc.returncode,
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
    }


def _is_repo(ws):
    res = _run(ws, "rev-parse", "--is-inside-work-tree")
    return res.get("exit_code") == 0


def _run_gh(ws, *args, timeout=60):
    """Run the GitHub CLI directly (NOT through `git`).

    `gh` speaks its own CLI, so it must not be wrapped by `_run`, which
    prepends `git` to every command.
    """

    try:
        proc = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(ws),
        )
    except subprocess.TimeoutExpired:
        return {"error": f"gh command timed out after {timeout}s"}
    except FileNotFoundError:
        return {"error": "GitHub CLI (gh) is not installed or not on PATH"}

    return {
        "exit_code": proc.returncode,
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
    }


def register(registry, config):
    registry.register(GitStatusTool(config.workspace))
    registry.register(GitDiffTool(config.workspace))
    registry.register(GitLogTool(config.workspace))
    registry.register(GitCommitTool(config.workspace))
    registry.register(GitCreatePrTool(config.workspace))


class GitStatusTool(Tool):
    def __init__(self, ws):
        super().__init__(
            name="git_status",
            description=(
                "Show the git working tree status and current branch of the "
                "workspace. Returns clean/dirty info and the list of changed "
                "files."
            ),
        )
        self.ws = ws

    def execute(self):
        if not _is_repo(self.ws):
            return {"error": "workspace is not a git repository"}

        res = _run(self.ws, "status", "--short", "--branch")
        if "error" in res:
            return res
        return {
            "branch": (res["stdout"].splitlines() or [""])[0].replace("## ", ""),
            "status": "\n".join(res["stdout"].splitlines()[1:]) or "(clean)",
        }


class GitDiffTool(Tool):
    def __init__(self, ws):
        super().__init__(
            name="git_diff",
            description=(
                "Show git diffs in the workspace. Use staged=true for staged "
                "changes (default: unstaged)."
            ),
            parameters={
                "staged": {"type": "boolean", "description": "Show staged changes"},
                "stat": {"type": "boolean", "description": "Only show diff stat"},
            },
        )
        self.ws = ws

    def execute(self, staged=False, stat=False):
        if not _is_repo(self.ws):
            return {"error": "workspace is not a git repository"}

        args = ["diff"]
        if staged:
            args.append("--staged")
        if stat:
            args.append("--stat")

        res = _run(self.ws, *args)
        if "error" in res:
            return res
        return {"diff": res["stdout"] or "(no changes)"}


class GitLogTool(Tool):
    def __init__(self, ws):
        super().__init__(
            name="git_log",
            description="Show recent git commit history of the workspace.",
            parameters={
                "n": {"type": "integer", "description": "Number of commits (default 10)"},
            },
        )
        self.ws = ws

    def execute(self, n=10):
        if not _is_repo(self.ws):
            return {"error": "workspace is not a git repository"}

        res = _run(self.ws, "log", "--oneline", f"-n{max(1, int(n))}")
        if "error" in res:
            return res
        return {"commits": res["stdout"] or "(no commits yet)"}


class GitCommitTool(Tool):
    def __init__(self, ws):
        super().__init__(
            name="git_commit",
            description=(
                "Stage changes and create a git commit in the workspace. "
                "Provide a clear, conventional commit message. If `files` is "
                "given, only those files are staged; otherwise all changes "
                "are staged. This is a write operation — it always asks the "
                "user for permission first."
            ),
            parameters={
                "message": {"type": "string", "description": "Commit message"},
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of file paths to stage",
                },
            },
            required=["message"],
        )
        self.ws = ws

    def execute(self, message, files=None):
        if not _is_repo(self.ws):
            return {"error": "workspace is not a git repository"}

        message = (message or "").strip()
        if not message:
            return {"error": "commit message is required"}

        if files:
            res = _run(self.ws, "add", "--", *files)
        else:
            res = _run(self.ws, "add", "-A")
        if "error" in res:
            return res
        if res.get("exit_code") != 0:
            return {"error": res.get("stderr") or "git add failed"}

        res = _run(self.ws, "commit", "-m", message)
        if "error" in res:
            return res
        if res.get("exit_code") != 0:
            return {"error": res.get("stderr") or "git commit failed"}

        return {
            "success": True,
            "action": "commit",
            "message": message,
            "output": res["stdout"],
        }


class GitCreatePrTool(Tool):
    def __init__(self, ws):
        super().__init__(
            name="git_create_pr",
            description=(
                "Create a pull request using the GitHub CLI (`gh`). Requires "
                "`gh` to be installed and authenticated. This is a write "
                "operation — it always asks the user for permission first."
            ),
            parameters={
                "title": {"type": "string", "description": "PR title"},
                "body": {"type": "string", "description": "PR description"},
                "base": {"type": "string", "description": "Base branch (optional)"},
                "head": {"type": "string", "description": "Head branch (optional)"},
            },
            required=["title"],
        )
        self.ws = ws

    def execute(self, title, body="", base="", head=""):
        if not _is_repo(self.ws):
            return {"error": "workspace is not a git repository"}

        if not subprocess.run(["gh", "--version"], capture_output=True, text=True).returncode == 0:
            return {"error": "GitHub CLI (gh) not found — install and authenticate it first"}

        args = ["pr", "create", "--title", title]
        if body:
            args += ["--body", body]
        if base:
            args += ["--base", base]
        if head:
            args += ["--head", head]

        res = _run_gh(self.ws, *args, timeout=60)
        if "error" in res:
            return res
        if res.get("exit_code") != 0:
            return {"error": res.get("stderr") or res.get("stdout") or "gh pr create failed"}

        return {
            "success": True,
            "action": "create_pr",
            "url": res["stdout"].strip(),
        }
