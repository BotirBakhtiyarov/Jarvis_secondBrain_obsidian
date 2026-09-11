# Contributing to ORION

Thanks for your interest in improving ORION! This guide covers everything you
need to go from a fresh clone to a merged pull request.

By participating you agree to follow our
[Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to contribute

- Report bugs or request features via the
  [issue templates](https://github.com/BotirBakhtiyarov/orion-second-brain/issues/new/choose).
- Improve documentation.
- Add tests for existing behaviour.
- Add or improve tools in `orion/plugins/`.
- Pick up a [good first issue](docs/good-first-issues.md).

## Development setup

ORION uses [uv](https://docs.astral.sh/uv/) as its package manager.

```bash
# 1. Fork the repo on GitHub, then clone your fork
git clone https://github.com/<your-username>/orion-second-brain.git
cd orion-second-brain

# 2. Install uv if you don't have it
#    https://docs.astral.sh/uv/getting-started/installation/

# 3. Install the project + all dev/optional groups (tests, Ruff, semantic, MCP)
uv sync
```

`uv sync` installs the `dev`, `mcp` and `semantic` dependency groups by default
(configured in `pyproject.toml`).

If you prefer pip: `pip install -e ".[dev]"` (add `mcp` and/or `semantic` extras
if you need them).

### Running ORION locally

```bash
cp .env.example .env   # then set DEEPSEEK_API_KEY and OBSIDIAN_VAULT
uv run orion
```

You do **not** need a real API key to work on most of the codebase — the test
suite never calls the API.

## Create a branch

```bash
git checkout -b feat/short-description   # or fix/..., docs/..., chore/...
```

Keep each branch focused on a single logical change.

## Tests

```bash
uv run pytest                     # full suite
uv run pytest -m "not network"    # skip tests that download models
uv run pytest tests/test_tools.py # a single file
```

Notes:

- `tests/test_mcp.py` needs the `mcp` extra and `tests/test_semantic.py` needs
  `fastembed`; both are skipped automatically when the extra is missing.
- The one test marked `@pytest.mark.network` downloads an embedding model on
  first run. It self-skips when offline, and CI runs with `-m "not network"`.

Please add tests for new behaviour. A new tool, in particular, should have at
least one test exercising `execute()`.

## Linting and formatting

ORION uses [Ruff](https://docs.astral.sh/ruff/) for both linting and formatting
(configured under `[tool.ruff]` in `pyproject.toml`).

```bash
uv run ruff check .            # lint
uv run ruff check . --fix      # auto-fix what's safe
uv run ruff format .           # format
uv run ruff format --check .   # verify formatting (what CI runs)
```

CI runs `ruff check .` and `ruff format --check .` — make sure both pass before
opening a PR.

## Coding conventions

- **Python 3.11+**. Use modern typing (`list[str]`, `str | None`).
- Keep functions small and focused; new tools live in `orion/plugins/` and
  subclass `orion.tools.Tool`.
- Add type hints to public functions and a short docstring when the "why" is
  not obvious.
- Match the surrounding style; Ruff/format is the source of truth.
- Never hardcode secrets or absolute paths. Configuration goes through
  `orion.config`.
- Keep dependencies minimal — do not add a library for something the standard
  library already does.
- Prefer improving an existing tool over adding a near-duplicate one.

## Commit messages

Write a short, imperative subject line describing the change, for example:

```text
Add git_commit tool
Fix semantic search hang on missing model
Document MCP configuration
```

Add a short body when the change needs context. Keep unrelated changes out of a
single commit.

## Pull request process

1. Make sure `uv run pytest -m "not network"`, `uv run ruff check .` and
   `uv run ruff format --check .` all pass locally.
2. Push your branch and open a pull request against `main`, filling in the PR
   template.
3. CI will run lint, format and the test matrix (Python 3.11–3.13). Address any
   failures.
4. A maintainer will review. Keep the discussion on the PR; push follow-up
   commits rather than force-pushing over review history.

## What makes a good contribution

- It solves a real, described problem (link an issue when possible).
- It is covered by tests and passes lint/format.
- It is small and focused, and does not change unrelated behaviour.
- It updates the docs (`README.md`, `docs/`) when it changes how ORION is used.

Thank you for contributing!
