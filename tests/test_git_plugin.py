import subprocess

import pytest

from orion.plugins.git_plugin import GitCommitTool, GitLogTool, GitStatusTool


@pytest.fixture
def repo(tmp_path):
    if subprocess.run(
        ["git", "--version"], capture_output=True, text=True
    ).returncode != 0:
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
