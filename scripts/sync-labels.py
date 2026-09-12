"""Create or update the repository labels from ``.github/labels.yml``.

Requires the [GitHub CLI](https://cli.github.com) installed and authenticated
(``gh auth login``) with write access to the repository.

Usage::

    uv run python scripts/sync-labels.py            # apply .github/labels.yml
    uv run python scripts/sync-labels.py --dry-run  # just print the commands
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS_FILE = ROOT / ".github" / "labels.yml"

_ENTRY = re.compile(
    r"- name:\s*(?P<name>.+?)\s*\n"
    r"\s*color:\s*\"?(?P<color>#?[0-9a-fA-F]{6})\"?\s*\n"
    r"\s*description:\s*(?P<description>.+)",
)


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse_labels(text: str) -> list[tuple[str, str, str]]:
    """Parse the small subset of YAML used by ``labels.yml``."""
    labels = []
    for match in _ENTRY.finditer(text):
        labels.append(
            (
                _unquote(match.group("name")),
                match.group("color").lstrip("#").lower(),
                _unquote(match.group("description")),
            )
        )
    return labels


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="print, do not run")
    args = parser.parse_args()

    labels = parse_labels(LABELS_FILE.read_text(encoding="utf-8"))
    if not labels:
        sys.exit(f"no labels parsed from {LABELS_FILE}")

    if not args.dry_run and shutil.which("gh") is None:
        sys.exit("the `gh` CLI is required (https://cli.github.com)")

    for name, color, description in labels:
        command = [
            "gh",
            "label",
            "create",
            name,
            "--color",
            color,
            "--description",
            description,
            "--force",
        ]
        if args.dry_run:
            print(" ".join(f'"{part}"' if " " in part else part for part in command))
            continue
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"!! {name}: {result.stderr.strip()}", file=sys.stderr)
            continue
        print(f"ok  {name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
