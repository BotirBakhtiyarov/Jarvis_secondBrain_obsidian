"""Render ``docs/demo-transcript.txt`` into ``img/demo.gif``.

This produces a *rendered illustration* of ORION's terminal UI — it is
deterministic and needs no API key, which keeps the README asset reproducible
in CI or on a fresh clone. For a genuine capture, record with
[asciinema](https://asciinema.org) instead::

    asciinema rec demo.cast
    agg demo.cast img/demo.gif

Usage::

    uv run --with pillow python scripts/make-demo-gif.py
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - developer convenience
    sys.exit("Pillow is required: uv run --with pillow python scripts/make-demo-gif.py")

ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPT = ROOT / "docs" / "demo-transcript.txt"
OUTPUT = ROOT / "img" / "demo.gif"

WIDTH, HEIGHT = 960, 600
TITLE_H = 34
PAD = 26
LINE_H = 22
FONT_SIZE = 16
FRAME_MS = 140
HOLD_MS = 2600

BG = (30, 30, 46)
BAR = (17, 17, 27)
FG = (205, 214, 244)
DIM = (127, 132, 156)
GREEN = (166, 227, 161)
YELLOW = (249, 226, 175)
BLUE = (137, 180, 250)
PROMPT = (148, 226, 213)

FONT_CANDIDATES = (
    "/usr/share/fonts/Adwaita/AdwaitaMono-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "/usr/share/fonts/TTF/DejaVuSansMono.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "C:/Windows/Fonts/consola.ttf",
)


def load_font(size: int = FONT_SIZE):
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def read_transcript() -> list[str]:
    lines = [
        line.rstrip()
        for line in TRANSCRIPT.read_text(encoding="utf-8").splitlines()
        if not line.startswith("#")
    ]
    while lines and not lines[0].strip():
        lines.pop(0)
    return normalize_box(lines)


def normalize_box(lines: list[str]) -> list[str]:
    """Pad ``│ …``/``╰…`` lines to match the width of the opening ``╭`` line."""
    top = next((ln for ln in lines if ln.startswith("╭")), None)
    if top is None:
        return lines

    inner = len(top) - 2
    fixed: list[str] = []
    for line in lines:
        if line.startswith("│"):
            fixed.append("│" + line[1:].ljust(inner)[:inner] + "│")
        elif line.startswith("╰"):
            fixed.append("╰" + "─" * inner + "╯")
        else:
            fixed.append(line)
    return fixed


def line_color(line: str) -> tuple[int, int, int]:
    stripped = line.strip()
    if line.startswith("$ "):
        return PROMPT
    if stripped and set(stripped) <= set("_/\\| "):
        return PROMPT  # ASCII-art banner
    if line.startswith("⏺"):
        return YELLOW
    if stripped.startswith("✓"):
        return GREEN
    if line.startswith("╭") or line.startswith("╰") or line.startswith("│"):
        return BLUE
    if line.startswith("Model ") or line.startswith("Type /help"):
        return DIM
    return FG


def render(lines: list[str], font, visible: int, max_lines: int) -> Image.Image:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, WIDTH, TITLE_H], fill=BAR)
    for i, color in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        draw.ellipse([20 + i * 22, 12, 32 + i * 22, 24], fill=color)
    draw.text((WIDTH // 2 - 62, 9), "orion — zsh", font=font, fill=DIM)

    y = TITLE_H + PAD
    for line in lines[: visible + 1][:max_lines]:
        draw.text((PAD, y), line, font=font, fill=line_color(line))
        y += LINE_H
    return img


def main() -> int:
    lines = read_transcript()
    font = load_font()
    max_lines = (HEIGHT - TITLE_H - PAD) // LINE_H
    lines = lines[:max_lines]

    frames = [render(lines, font, n, max_lines) for n in range(len(lines))]
    frames.append(render(lines, font, len(lines), max_lines))

    palette = frames[-1].quantize(colors=64)
    frames = [frame.quantize(palette=palette) for frame in frames]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        OUTPUT,
        save_all=True,
        append_images=frames[1:],
        duration=[*[FRAME_MS] * (len(frames) - 1), HOLD_MS],
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(
        f"wrote {OUTPUT.relative_to(ROOT)} "
        f"({OUTPUT.stat().st_size // 1024} KB, {len(frames)} frames)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
