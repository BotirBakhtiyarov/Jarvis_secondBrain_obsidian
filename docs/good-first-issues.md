# Good first issues

These are self-contained tasks that are a great way to get familiar with ORION.
Pick one, open an issue (or comment on an existing one) to claim it, and follow
[CONTRIBUTING.md](../CONTRIBUTING.md).

Each task lists its difficulty, goal, steps, expected result and the files to
inspect.

---

## 1. Add tests for configuration and CLI parsing

**Difficulty:** Easy

**Goal:** `orion/config.py` and the CLI parser in `orion/main.py` currently have
no dedicated tests. Add a test file that covers their behaviour.

**Steps:**

1. Read `orion/config.py` and `parse_args()` in `orion/main.py`.
2. Create `tests/test_config.py`.
3. Using `monkeypatch.setenv`, assert:
   - `load_config()` raises `ValueError` when `OBSIDIAN_VAULT` is not set.
   - `DEEPSEEK_MODEL` and `WORKSPACE` fall back to their defaults.
   - CLI-style `overrides` win over environment variables.
4. Add tests for `parse_args([...])`:
   - no arguments → empty `query`.
   - `["hello", "world"]` → `query == ["hello", "world"]`.
   - `["config"]` → `command == "config"`.
   - `["config", "--init"]` → `config_init is True`.

**Expected result:** `uv run pytest tests/test_config.py` passes, and the tests
fail if the corresponding behaviour is broken.

**Relevant files:** `orion/config.py`, `orion/main.py`, `tests/test_workspace.py`
(for a style example).

---

## 2. Warn when the Obsidian vault path does not exist

**Difficulty:** Easy

**Goal:** Today, if `OBSIDIAN_VAULT` points to a folder that does not exist,
ORION starts silently and memory tools return empty results. Print a clear
warning instead, without crashing.

**Steps:**

1. Read `orion/config.py` (`load_config`) and the startup code in
   `orion/main.py` (`main`).
2. After the config is loaded, if `config.obsidian_vault` is not an existing
   directory, print a warning (use `orion.ui.console`) that shows the resolved
   path and suggests checking `OBSIDIAN_VAULT`.
3. Do **not** raise — ORION should still start.
4. Add a small test using `tmp_path` that checking a missing path is detected.

**Expected result:** Starting ORION with a bad vault path prints a helpful
warning; a valid path prints nothing.

**Relevant files:** `orion/main.py`, `orion/config.py`, `tests/test_config.py`.

---

## 3. Add tests for session persistence

**Difficulty:** Easy

**Goal:** `orion/memory.py` (session save/resume) has no tests. Cover the main
functions.

**Steps:**

1. Read `orion/memory.py`.
2. Create `tests/test_memory.py`.
3. Using `tmp_path` as the history path, assert:
   - `save_session()` creates a JSON file and a `latest.json`.
   - `load_latest()` returns the saved messages.
   - `load_session(id)` finds a session by full id and by prefix.
   - `_clean_tail()` drops a trailing partial tool call.
4. Keep the tests independent of the network and the API.

**Expected result:** `uv run pytest tests/test_memory.py` passes.

**Relevant files:** `orion/memory.py`, `tests/test_git_plugin.py` (for a
`tmp_path` fixture example).

---

## 4. Expose and document the `run_command` timeout

**Difficulty:** Easy

**Goal:** `RunCommandTool.execute` accepts a `timeout` argument (default 60s),
but it is not declared in the tool's `parameters`, so the model cannot set it.
Expose it and document it.

**Steps:**

1. Read `orion/plugins/code_plugin.py` (`RunCommandTool`).
2. Add a `timeout` entry to `parameters` (type `integer`, describe the default
   and the unit) so the model can control it.
3. Update the tool description to mention the timeout.
4. Add a test that calling `execute()` with a tiny timeout returns an `error`
   for a long-running command (e.g. `sleep 5` on POSIX, skipped on Windows).

**Expected result:** `/tools` shows the new parameter and the test passes.

**Relevant files:** `orion/plugins/code_plugin.py`, `tests/test_tools.py`.

---

## 5. Improve `web_search` error handling

**Difficulty:** Medium

**Goal:** `orion/plugins/web_plugin.py` returns a generic message for network
problems. Return clearer, actionable errors for HTTP errors (bad Tavily key,
rate limiting, server errors) and cover them with tests.

**Steps:**

1. Read `orion/plugins/web_plugin.py` (`_http_json`, `web_search`).
2. Catch `urllib.error.HTTPError` separately and include the status code and a
   short hint (e.g. 401 → check `TAVILY_API_KEY`).
3. Keep the current behaviour of never raising — always return `{"error": ...}`.
4. Add tests that monkeypatch `_http_json` (or `urllib.request.urlopen`) to
   raise `HTTPError` and assert the returned error message.

**Expected result:** `uv run pytest tests/test_web_plugin.py` passes and the
error messages are more helpful.

**Relevant files:** `orion/plugins/web_plugin.py`, `tests/test_web_plugin.py`.

---

## 6. Add a demo recording to the README

**Difficulty:** Easy (documentation)

**Goal:** The README has a "Demo" section with only the startup banner. Record a
short terminal session (an animated GIF or an
[asciinema](https://asciinema.org/) cast) showing a real interaction, and embed
it.

**Steps:**

1. Install ORION locally (`uv sync`, configure `.env`).
2. Record a short session (10–20s) that shows: starting ORION, a question, a
   tool call, and saving a note.
3. Save the asset under `docs/` (e.g. `docs/demo.gif`).
4. Replace the banner-only Demo section in `README.md` with the recording, and
   keep the banner text as a fallback.

**Expected result:** The README shows a real demo, and the asset is committed
(keep it reasonably small).

**Relevant files:** `README.md`, `docs/`.
