# Good first issues

A curated list of self-contained tasks that are a great way to get familiar
with ORION. Pick one, **comment on its issue to claim it**, and follow
[CONTRIBUTING.md](../CONTRIBUTING.md).

New here? Start with anything marked **Easy** — none of them require deep
knowledge of the codebase.

## Labels

We tag approachable work so you can filter it on the
[issue list](https://github.com/BotirBakhtiyarov/orion-second-brain/issues):

| Label | Meaning |
|---|---|
| [`good first issue`](https://github.com/BotirBakhtiyarov/orion-second-brain/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) | Small, self-contained, safe to try as a first PR |
| [`help wanted`](https://github.com/BotirBakhtiyarov/orion-second-brain/issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22) | Maintainers would welcome a hand; may be larger |
| `difficulty: easy` | No architecture knowledge needed |
| `difficulty: medium` | A little familiarity with the codebase helps |
| `documentation` | Docs-only change |
| `enhancement` / `bug` | Feature request / defect |

If an unlabelled issue looks approachable, just say so in a comment — we will
happily hand it over. The label set lives in
[`.github/labels.yml`](../.github/labels.yml).

---

## 1. Warn when the Obsidian vault path does not exist

**Difficulty:** Easy · **Labels:** `good first issue`, `difficulty: easy`

**Goal:** Today, if `OBSIDIAN_VAULT` points to a folder that does not exist,
ORION starts silently and memory tools return empty results. Print a clear
warning instead, without crashing.

**Steps:**

1. Read `orion/config.py` (`load_config`) and the startup code in
   `orion/main.py` (`main`).
2. After the config is loaded, if `config.obsidian_vault` is not an existing
   directory, print a warning (use `orion.ui.console`) showing the resolved
   path and suggesting they check `OBSIDIAN_VAULT`.
3. Do **not** raise — ORION should still start.
4. Add a small test using `tmp_path` that a missing path is detected.

**Expected result:** Starting ORION with a bad vault path prints a helpful
warning; a valid path prints nothing.

**Relevant files:** `orion/main.py`, `orion/config.py`, `tests/test_config.py`.

---

## 2. Add tests for session persistence

**Difficulty:** Easy · **Labels:** `good first issue`, `difficulty: easy`

**Goal:** `orion/memory.py` (session save/resume) has no dedicated tests.
(`tests/test_memory_plugin.py` covers the memory *tool*, not this module.)
Cover the main functions.

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

## 3. Expose and document the `run_command` timeout

**Difficulty:** Easy · **Labels:** `good first issue`, `difficulty: easy`

**Goal:** `RunCommandTool.execute` accepts a `timeout` argument (default 60s),
but it is not declared in the tool's `parameters`, so the model cannot set it.
Expose it and document it.

**Steps:**

1. Read `orion/plugins/code_plugin.py` (`RunCommandTool`).
2. Add a `timeout` entry to `parameters` (type `integer`, describe the unit and
   the default) so the model can control it.
3. Update the tool description to mention the timeout.
4. Add a test that calling `execute()` with a tiny timeout returns an `error`
   for a long-running command (e.g. `sleep 5` on POSIX; skip on Windows).

**Expected result:** `/tools` shows the new parameter and the test passes.

**Relevant files:** `orion/plugins/code_plugin.py`, `tests/test_tools.py`.

---

## 4. Improve `web_search` error handling

**Difficulty:** Medium · **Labels:** `help wanted`, `difficulty: medium`

**Goal:** `orion/plugins/web_plugin.py` returns a generic message for network
problems. Return clearer, actionable errors for HTTP errors (bad Tavily key,
rate limiting, server errors) and cover them with tests.

**Steps:**

1. Read `orion/plugins/web_plugin.py` (`_http_json`, `web_search`).
2. Catch `urllib.error.HTTPError` separately and include the status code with a
   short hint (e.g. 401 → check `TAVILY_API_KEY`, 429 → slow down).
3. Keep the current behaviour of never raising — always return `{"error": ...}`.
4. Add tests that monkeypatch `urlopen` to raise `HTTPError` and assert the
   returned message.

**Expected result:** `uv run pytest tests/test_web_plugin.py` passes and the
error messages are more helpful.

**Relevant files:** `orion/plugins/web_plugin.py`, `tests/test_web_plugin.py`.

---

## 5. Add a `--json` flag to `orion schedule list`

**Difficulty:** Easy · **Labels:** `good first issue`, `difficulty: easy`

**Goal:** The scheduler stores jobs as JSON, but there is no way to read them
from a script. Add `orion schedule list --json` that prints the job list as
JSON instead of a table.

**Steps:**

1. Read `run_schedule_command()` in `orion/main.py` and `orion/scheduler.py`.
2. When `--json` is present, print `json.dumps([asdict(j) for j in jobs])`
   (no Rich table, no colours) and return.
3. Keep the current table output as the default.
4. Add a test that the serialised output is valid JSON and round-trips through
   `scheduler.load_jobs`.

**Expected result:** `orion schedule list --json | python -m json.tool` works.

**Relevant files:** `orion/main.py`, `orion/scheduler.py`, `tests/test_scheduler.py`.

---

## 6. Add an `orion doctor` command

**Difficulty:** Medium · **Labels:** `help wanted`, `difficulty: medium`

**Goal:** When something is misconfigured, the error appears deep in a session.
Add `orion doctor` that checks the environment up front and prints a short
report.

**Steps:**

1. Create `orion/doctor.py` with `run_checks(config) -> list[tuple[str, bool, str]]`
   (name, ok, detail).
2. Check at least: `.env` exists; `OBSIDIAN_VAULT` is a directory; the provider
   API key is set; the workspace is a git repository; the history file is
   writable.
3. Wire it into `parse_args()` / `main()` next to the `config` command, and
   print ✅/⚠️ lines with `orion.ui.console`.
4. Add `tests/test_doctor.py` using `tmp_path` and `monkeypatch.setenv`.

**Expected result:** `orion doctor` prints a readable checklist and exits 0.

**Relevant files:** `orion/main.py`, `orion/config.py`, `tests/test_config.py`.

---

## 7. Record a real demo recording to replace the rendered GIF

**Difficulty:** Easy · **Labels:** `good first issue`, `documentation`

**Goal:** `img/demo.gif` is a *rendered illustration* produced by
`scripts/make-demo-gif.py` from `docs/demo-transcript.txt`. Replace it with a
genuine capture of a real session.

**Steps:**

1. Install ORION locally (`uv sync`, configure `.env`).
2. Record 15–25s that shows: starting ORION, a question, a tool call, and a note
   saved to the vault.
3. Convert the cast to a GIF:
   `asciinema rec demo.cast && agg demo.cast img/demo.gif`
   (keep the result well under ~2 MB).
4. Update the caption in the README so it no longer says "rendered preview",
   and keep `scripts/make-demo-gif.py` as the offline fallback.

**Expected result:** The README shows a real recording.

**Relevant files:** `README.md`, `img/`, `scripts/make-demo-gif.py`.

---

## 8. Document project instructions (`ORION.md`) in the README

**Difficulty:** Easy · **Labels:** `good first issue`, `documentation`

**Goal:** ORION reads an optional `ORION.md` from the workspace and appends it
to the system prompt, but the README never mentions it.

**Steps:**

1. Read `build_system()` in `orion/main.py`.
2. Add a short **Project instructions** section to the README: what `ORION.md`
   is, where it is read from, and a tiny example.
3. Link it from the features list.

**Expected result:** A reader can discover and use `ORION.md`.

**Relevant files:** `README.md`, `orion/main.py`.

---

## Adding your own

Found something else? Ideas that make good first issues:

- Small gaps with an obvious, testable outcome.
- Documentation that is missing or out of date.
- A tool or CLI flag that is nearly trivial to add.

Open an issue describing the goal, the steps and the files involved, then
label it `good first issue`.
