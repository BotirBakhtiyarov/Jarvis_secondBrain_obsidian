import json
import time
from pathlib import Path


def sessions_dir(history_path: Path) -> Path:
    return history_path.parent / "sessions"


def _clean_tail(messages: list[dict]) -> list[dict]:
    """Yarim qolgan tool chaqiruvi bilan tugagan sessiyani tozalaydi.

    Resume qilingan suhbat hech qachon yarim tool chaqiruvidan boshlamasligi
    uchun oxirgi to'liq assistant javobigacha kesib olinadi.
    """

    cut = None
    for i in range(len(messages) - 1, -1, -1):
        m = messages[i]
        if (
            m.get("role") == "assistant"
            and m.get("content")
            and not m.get("tool_calls")
        ):
            cut = i + 1
            break
    return messages[:cut] if cut is not None else []


def save_session(history_path: Path, messages: list[dict]) -> Path:
    """Suhbatni vaqt belgili sessiya fayliga va latest.json'ga saqlaydi."""

    d = sessions_dir(history_path)
    d.mkdir(parents=True, exist_ok=True)

    payload = [m for m in messages if m.get("role") != "system"]
    sid = time.strftime("%Y%m%d_%H%M%S")

    path = d / f"{sid}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    (d / "latest.json").write_text(
        json.dumps({"id": sid, "path": str(path)}, ensure_ascii=False),
        encoding="utf-8",
    )

    return path


def load_session(history_path: Path, session_id: str) -> list[dict] | None:
    """ID yoki ID prefiksi bo'yicha sessiyani yuklaydi."""

    d = sessions_dir(history_path)
    if not d.exists():
        return None

    for p in sorted(d.glob("*.json"), reverse=True):
        if p.stem == "latest":
            continue
        if p.stem.startswith(session_id) or session_id in p.stem:
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, list):
                return _clean_tail(data)
    return None


def load_latest(history_path: Path) -> list[dict]:
    d = sessions_dir(history_path)
    if not d.exists():
        return []

    latest = d / "latest.json"
    if not latest.exists():
        return []

    try:
        meta = json.loads(latest.read_text(encoding="utf-8"))
        path = Path(meta.get("path", ""))
    except (OSError, json.JSONDecodeError):
        return []

    if not path.exists():
        return []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    return _clean_tail(data) if isinstance(data, list) else []


def list_sessions(history_path: Path, limit: int = 10) -> list[dict]:
    d = sessions_dir(history_path)
    if not d.exists():
        return []

    out = []
    for p in sorted(d.glob("*.json"), reverse=True):
        if p.stem == "latest":
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, list):
            continue

        first = next(
            (m.get("content", "") for m in data if m.get("role") == "user"),
            "",
        )
        out.append(
            {
                "id": p.stem,
                "first": (first[:60] + "…") if len(first) > 60 else first,
                "messages": len(data),
            }
        )
        if len(out) >= limit:
            break
    return out
