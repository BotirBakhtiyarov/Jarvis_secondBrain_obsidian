import subprocess

import pytest

from orion.plugins.git_plugin import (
    GitCommitTool,
    GitCreatePrTool,
    GitLogTool,
    GitStatusTool,
)


@pytest.fixture
def repo(tmp_path):
    if subprocess.run(["git", "--version"], capture_output=True, text=True).returncode != 0:
        pytest.skip("git not available")

    for args in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "Test User"],
    ):
        subprocess.run(args, cwd=str(tmp_path), check=True, capture_output=True)
    return tmp_path


def test_git_status_shows_untracked(repo):
    (repo / "a.txt").write_text("hello\n", encoding="utf-8")

    res = GitStatusTool(repo).execute()
    assert "a.txt" in res["status"]


def test_git_commit_and_log(repo):
    (repo / "a.txt").write_text("hello\n", encoding="utf-8")

    res = GitCommitTool(repo).execute("initial commit")
    assert res["success"] is True
    assert res["action"] == "commit"

    assert GitStatusTool(repo).execute()["status"] == "(clean)"

    log = GitLogTool(repo).execute()
    assert "initial commit" in log["commits"]


def test_git_commit_requires_message(repo):
    (repo / "a.txt").write_text("hello\n", encoding="utf-8")
    res = GitCommitTool(repo).execute("")
    assert "error" in res


def _gh_fake_run(calls):
    """Stub that records every git/gh invocation."""

    def fake_run(cmd, *args, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(
            cmd, 0, stdout="https://github.com/x/pull/1\n", stderr=""
        )

    return fake_run


def test_git_create_pr_runs_gh_directly(repo, monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr("orion.plugins.git_plugin.subprocess.run", _gh_fake_run(calls))

    tool = GitCreatePrTool(repo)
    res = tool.execute("My PR title", body="body", base="main")

    assert res["success"] is True
    assert res["url"] == "https://github.com/x/pull/1"

    # gh must run directly, not via `git` — regression guard for the old bug
    pr_call = next(cmd for cmd in calls if cmd[0] == "gh" and cmd[1:3] == ["pr", "create"])
    assert pr_call == [
        "gh",
        "pr",
        "create",
        "--title",
        "My PR title",
        "--body",
        "body",
        "--base",
        "main",
    ]
    assert all(cmd[0] != "git" or cmd[1:2] != ["gh"] for cmd in calls)
