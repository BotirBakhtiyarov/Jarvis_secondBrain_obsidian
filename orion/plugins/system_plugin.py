import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from orion.tools import Tool


def register(registry, config):
    registry.register(GetTimeTool())
    registry.register(OpenUrlTool())
    registry.register(OpenAppTool())
    registry.register(NotifyTool())
    registry.register(ClipboardCopyTool())
    registry.register(ClipboardReadTool())
    registry.register(ScreenshotTool())


def _run(cmd, timeout=30):
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return {"error": f"Command timed out after {timeout}s"}
    except FileNotFoundError as err:
        return {"error": f"Required command not found: {err.filename}"}
    except Exception as err:  # noqa: BLE001
        return {"error": f"{type(err).__name__}: {err}"}

    return {
        "exit_code": proc.returncode,
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
    }


class GetTimeTool(Tool):
    def __init__(self):
        super().__init__(
            name="get_time",
            description=(
                "Get the current date and time (local timezone). Use this "
                "whenever the task involves dates, deadlines, scheduling, "
                "or any 'today'/'now' reference."
            ),
        )

    def execute(self):
        now = datetime.now().astimezone()
        return {
            "iso": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "weekday": now.strftime("%A"),
            "timezone": str(now.tzinfo),
            "tz_offset": now.strftime("%z"),
        }


class OpenUrlTool(Tool):
    def __init__(self):
        super().__init__(
            name="open_url",
            description="Open a URL in the default browser.",
            parameters={"url": {"type": "string", "description": "Full URL (http/https)"}},
            required=["url"],
        )

    def execute(self, url):
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            return {"error": "URL http/https bilan boshlanishi kerak"}

        if sys.platform == "darwin":
            cmd = ["open", url]
        elif sys.platform == "win32":
            cmd = ["cmd", "/c", "start", "", url]
        else:
            cmd = ["xdg-open", url]

        res = _run(cmd, timeout=15)
        if res.get("exit_code") == 0 and "error" not in res:
            return {"success": True, "opened": url}
        return res


class OpenAppTool(Tool):
    def __init__(self):
        super().__init__(
            name="open_app",
            description=(
                "Launch an application by name (must be on PATH) or by path."
            ),
            parameters={
                "name": {
                    "type": "string",
                    "description": "App name (e.g. 'code', 'firefox') or path",
                }
            },
            required=["name"],
        )

    def execute(self, name):
        path = shutil.which(name)
        if not path:
            candidate = Path(name).expanduser()
            if candidate.exists():
                path = str(candidate)
            else:
                return {"error": f"App not found: {name}"}

        try:
            subprocess.Popen(
                [path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception as err:  # noqa: BLE001
            return {"error": f"{type(err).__name__}: {err}"}

        return {"success": True, "launched": path}


class NotifyTool(Tool):
    def __init__(self):
        super().__init__(
            name="notify",
            description="Send a desktop notification.",
            parameters={
                "title": {"type": "string", "description": "Notification title"},
                "message": {"type": "string", "description": "Notification body"},
            },
            required=["title", "message"],
        )

    def execute(self, title, message):
        if sys.platform == "darwin":
            script = (
                f'display notification "{message}" with title "{title}"'
            )
            return _run(["osascript", "-e", script], timeout=15)
        if sys.platform == "win32":
            return {"error": "Windows not yet supported"}

        return _run(["notify-send", title, message], timeout=15)


class ClipboardCopyTool(Tool):
    def __init__(self):
        super().__init__(
            name="clipboard_copy",
            description="Copy text to the system clipboard.",
            parameters={"text": {"type": "string", "description": "Text to copy"}},
            required=["text"],
        )

    def execute(self, text):
        try:
            if sys.platform == "darwin":
                proc = subprocess.run(
                    ["pbcopy"], input=text, text=True, timeout=15
                )
            elif sys.platform == "win32":
                proc = subprocess.run(
                    ["clip"], input=text, text=True, timeout=15
                )
            elif shutil.which("wl-copy"):
                proc = subprocess.run(
                    ["wl-copy"], input=text, text=True, timeout=15
                )
            elif shutil.which("xclip"):
                proc = subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=text, text=True, timeout=15,
                )
            else:
                return {"error": "Clipboard tool not found (xclip/wl-copy)"}
        except FileNotFoundError as err:
            return {"error": f"Command not found: {err.filename}"}

        return {"success": proc.returncode == 0}


class ClipboardReadTool(Tool):
    def __init__(self):
        super().__init__(
            name="clipboard_read",
            description="Read text from the system clipboard.",
        )

    def execute(self):
        try:
            if sys.platform == "darwin":
                cmd = ["pbpaste"]
            elif sys.platform == "win32":
                return _run(
                    ["powershell", "-Command", "Get-Clipboard"], timeout=15
                )
            elif shutil.which("wl-paste"):
                cmd = ["wl-paste"]
            elif shutil.which("xclip"):
                cmd = ["xclip", "-selection", "clipboard", "-o"]
            else:
                return {"error": "Clipboard tool not found (xclip/wl-paste)"}
        except FileNotFoundError as err:
            return {"error": f"Command not found: {err.filename}"}

        return _run(cmd, timeout=15)


class ScreenshotTool(Tool):
    def __init__(self):
        super().__init__(
            name="screenshot",
            description=(
                "Capture a screenshot of the screen and save it to a file "
                "(default: ~/orion_screenshot_TIMESTAMP.png)."
            ),
            parameters={
                "path": {
                    "type": "string",
                    "description": "Output file path (optional)",
                }
            },
        )

    def execute(self, path=""):
        if not path:
            path = str(
                Path.home()
                / f"orion_screenshot_{time.strftime('%Y%m%d_%H%M%S')}.png"
            )

        if sys.platform == "darwin":
            res = _run(["screencapture", "-x", path], timeout=30)
        elif sys.platform == "win32":
            res = _run(
                [
                    "powershell",
                    "-Command",
                    "Add-Type -AssemblyName System.Windows.Forms;"
                    "$b = [System.Windows.Forms.SystemInformation]::VirtualScreen;"
                    f"$img = New-Object System.Drawing.Bitmap($b.Width,$b.Height);"
                    "$g = [System.Drawing.Graphics]::FromImage($img);"
                    "$g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size);"
                    f'$img.Save("{path}");',
                ],
                timeout=30,
            )
        else:
            res = self._linux(path)

        if res and res.get("error"):
            return res
        if res and res.get("exit_code") not in (0, None):
            return res

        if Path(path).exists():
            return {"success": True, "path": path}
        return {"error": "Screenshot saqlanmadi", "path": path}

    def _linux(self, path):
        for cmd in (
            ["scrot", path],
            ["gnome-screenshot", "-f", path],
            ["import", "-window", "root", path],
            ["grim", path],
        ):
            if shutil.which(cmd[0]):
                res = _run(cmd, timeout=30)
                if res.get("exit_code") == 0:
                    return res
        return {"error": "Screenshot tool topilmadi (scrot/import/grim)"}
