import html
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from lecture_study.config import (
    AUDIO_EXTENSIONS,
    ConfigError,
    Settings,
    load_settings,
    onedrive_roots,
    validate,
    windows_drive_type,
)
from lecture_study.hold import resume
from lecture_study.jobs import Job
from lecture_study.scanner import find_stable_recordings

PAGE_HOST = "127.0.0.1"
PAGE_PORT = 8765
PRODUCTS = ("report.md", "transcript.md", "notes.md", "mindmap.md", "questions.md")
_SHA = re.compile(r"^[0-9a-fA-F]{64}$")


class PageAddressError(Exception):
    pass


class PortTaken(Exception):
    pass


class RejectedExtension(Exception):
    pass


def bind_page(host: str = PAGE_HOST, port: int = PAGE_PORT) -> object:
    if host != PAGE_HOST or port != PAGE_PORT:
        raise PageAddressError(f"{host}:{port}")
    server = ThreadingHTTPServer((host, port), StudyHandler)
    return server


def serve_and_watch(watch, host: str = PAGE_HOST, port: int = PAGE_PORT) -> int:
    try:
        server = bind_page(host, port)
    except (OSError, PortTaken, PageAddressError):
        return 1
    try:
        watch()
    finally:
        server.server_close()
    return 0


def remember_paths(
    config: Path,
    watch: Path,
    library: Path,
    *,
    roots: list[Path],
    drive_type,
) -> bool:
    current = load_settings(config) if config.exists() else Settings()
    candidate = replace(current, watch_dir=watch, library_dir=library)
    try:
        validate(candidate, roots=roots, drive_type=drive_type)
    except ConfigError:
        return False
    text = config.read_text(encoding="utf-8") if config.exists() else ""
    text = _assign(text, "watch_dir", watch.as_posix())
    text = _assign(text, "library_dir", library.as_posix())
    config.write_text(text, encoding="utf-8")
    return True


def chosen_recordings(folder: Path | None, file: Path | None, *, now: float, stable_seconds: int) -> list[Path]:
    if file is not None:
        if file.suffix.lower() not in AUDIO_EXTENSIONS:
            raise RejectedExtension(file.name)
        if now - file.stat().st_mtime < stable_seconds:
            return []
        return [file]
    return [item.path for item in find_stable_recordings(folder, stable_seconds=stable_seconds, now=now)]


def choose_folders(config: Path, watch: Path, library: Path) -> str:
    StudyHandler.draft_watch = None
    StudyHandler.draft_library = None
    if not str(watch).strip() or not str(library).strip():
        StudyHandler.notice = "Both folders are required."
        return StudyHandler.notice
    if not remember_paths(config, watch, library, roots=onedrive_roots(), drive_type=windows_drive_type):
        try:
            nested = watch.resolve() == library.resolve() or watch.resolve() in library.resolve().parents
        except OSError:
            nested = False
        if nested:
            StudyHandler.notice = "The results folder cannot sit inside the audio folder. The folders already in use stay."
        else:
            StudyHandler.notice = "Those folders were rejected. The previous ones stay."
        return StudyHandler.notice
    stored = load_settings(config)
    StudyHandler.watch = stored.watch_dir
    StudyHandler.library = stored.library_dir
    StudyHandler.notice = ""
    return ""


def apply_picked(which: str, picked: Path | None) -> str:
    if picked is None:
        return ""
    if not picked.is_dir():
        StudyHandler.notice = "That folder does not exist."
        return StudyHandler.notice
    watch = StudyHandler.watch
    library = StudyHandler.library
    if which == "watch":
        watch = picked
    elif which == "library":
        library = picked
    else:
        return ""
    if StudyHandler.config is None:
        StudyHandler.notice = "Configuration is not available."
        return StudyHandler.notice
    return choose_folders(StudyHandler.config, watch, library)


def pick_directory(title: str, initial: Path | None = None) -> Path | None:
    if os.name == "nt":
        return _pick_windows(title, initial)
    if sys.platform == "darwin":
        return _pick_mac(title, initial)
    return None


def _pick_windows(title: str, initial: Path | None) -> Path | None:
    script = "\n".join([
        "Add-Type -AssemblyName System.Windows.Forms",
        "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog",
        "$dialog.Description = $env:PICK_TITLE",
        "$dialog.ShowNewFolderButton = $true",
        "if ($env:PICK_INITIAL -and (Test-Path -LiteralPath $env:PICK_INITIAL)) { $dialog.SelectedPath = $env:PICK_INITIAL }",
        "$owner = New-Object System.Windows.Forms.Form",
        "$owner.TopMost = $true",
        "$owner.StartPosition = 'CenterScreen'",
        "$owner.ShowInTaskbar = $false",
        "$owner.Show()",
        "$result = $dialog.ShowDialog($owner)",
        "$owner.Close()",
        "if ($result -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $dialog.SelectedPath }",
    ])
    return _picked_path(_run_picker(["powershell", "-NoProfile", "-STA", "-Command", script], title, initial))


def _pick_mac(title: str, initial: Path | None) -> Path | None:
    prompt = title.replace('"', "'")
    location = ""
    if initial is not None and initial.is_dir():
        location = f' default location POSIX file "{initial.as_posix()}"'
    script = f'POSIX path of (choose folder with prompt "{prompt}"{location})'
    completed = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        return None
    return _picked_path(completed.stdout)


def _run_picker(command: list[str], title: str, initial: Path | None) -> str:
    env = os.environ.copy()
    env["PICK_TITLE"] = title
    env["PICK_INITIAL"] = "" if initial is None else str(initial)
    completed = subprocess.run(command, capture_output=True, text=True, env=env, check=False)
    if completed.returncode != 0:
        return ""
    return completed.stdout


def _picked_path(output: str) -> Path | None:
    chosen = output.strip()
    if not chosen:
        return None
    path = Path(chosen)
    return path if path.is_dir() else None


def lecture_section(library: Path, watch: Path | None = None, hold: Path | None = None) -> str:
    held = hold is not None and hold.is_file()
    jobs = _jobs_by_source(library)
    files = _audio_files(watch)
    seen: set[Path] = set()
    rows = []
    for path in files:
        resolved = path.resolve()
        seen.add(resolved)
        rows.append(_progress_row(path.name, jobs.get(resolved), held=held, library=library))
    for resolved, job in jobs.items():
        if resolved in seen:
            continue
        rows.append(_progress_row(resolved.name, job, held=held, library=library))
    summary = _progress_summary(rows, held=held, has_audio=bool(files) or bool(jobs))
    resume = ""
    if held and not any(row[2] for row in rows):
        resume = '<form method="post" action="/hold"><button name="action" value="resume">Resume</button></form>'
    caption = f"<p>Results in use: {html.escape(library.as_posix())}</p><p>{html.escape(summary)}</p>{resume}"
    body = "".join(row[0] for row in rows)
    return caption + f"<table>{body}</table>"


def _audio_files(watch: Path | None) -> list[Path]:
    if watch is None or not watch.is_dir():
        return []
    found = [path for path in watch.rglob("*") if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS]
    return sorted(found, key=lambda path: path.name.lower())


def _jobs_by_source(library: Path) -> dict[Path, dict]:
    found: dict[Path, dict] = {}
    if not library.is_dir():
        return found
    for directory in library.iterdir():
        if not directory.is_dir():
            continue
        source = _json(directory / "source.json")
        state = _json(directory / "state.json")
        raw = str(source.get("path", ""))
        if not raw:
            continue
        try:
            key = Path(raw).resolve()
        except OSError:
            continue
        state["sha"] = directory.name
        found[key] = state
    return found


def _progress_row(name: str, job: dict | None, *, held: bool, library: Path) -> tuple[str, str, bool]:
    status = str(job.get("status") or "") if job else ""
    stage = (job.get("stage") if job else None) or "-"
    stopped = status == "stopped"
    if not status:
        status = "on hold" if held else "queued"
    resume = ""
    links = ""
    if job is not None:
        directory = library / str(job["sha"])
        links = " ".join(
            f'<a href="/files/{job["sha"]}/{product}">{product}</a>'
            for product in PRODUCTS
            if (directory / product).is_file()
        )
        if stopped:
            resume = (
                f'<form method="post" action="/hold"><input type="hidden" name="job" value="{job["sha"]}">'
                '<button name="action" value="resume">Resume</button></form>'
            )
    html_row = (
        "<tr><td>"
        + html.escape(name)
        + "</td><td>"
        + html.escape(str(stage))
        + "</td><td>"
        + html.escape(status)
        + "</td><td>"
        + links
        + "</td><td>"
        + resume
        + "</td></tr>"
    )
    return html_row, status, stopped


def _progress_summary(rows: list[tuple[str, str, bool]], *, held: bool, has_audio: bool) -> str:
    if not has_audio:
        return "No audio files in the folder in use."
    if held:
        return "Processing is stopped. Files stay put until you press Resume."
    statuses = [status for _, status, _ in rows]
    if "running" in statuses:
        return "A file is running. Its stage is in the table."
    if "queued" in statuses:
        return "Files are queued. The first one starts at the next check."
    return "Nothing is running."


def render_page(
    library: Path,
    *,
    ollama_up: bool,
    watch: Path | None = None,
    library_field: Path | None = None,
    notice: str = "",
    hold: Path | None = None,
) -> str:
    ollama = "Ollama: responding" if ollama_up else "Ollama: not responding"
    shown_watch = "" if watch is None else watch.as_posix()
    shown_library = (library if library_field is None else library_field).as_posix()
    notice_html = f"<p>{html.escape(notice)}</p>" if notice else ""
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\"></head><body>"
        f"<p>{ollama}</p>"
        "<form method=\"post\" action=\"/paths\">"
        f"<label>Audio folder <input name=\"watch\" value=\"{html.escape(shown_watch, quote=True)}\" size=\"80\"></label> "
        "<button type=\"submit\" formaction=\"/pick\" name=\"which\" value=\"watch\">Choose audio folder</button> "
        "<button type=\"submit\" formaction=\"/hold\" name=\"action\" value=\"stop\">Stop</button><br>"
        f"<label>Results folder <input name=\"library\" value=\"{html.escape(shown_library, quote=True)}\" size=\"80\"></label> "
        "<button type=\"submit\" formaction=\"/pick\" name=\"which\" value=\"library\">Choose results folder</button><br>"
        "<button type=\"submit\">Use these folders</button></form>"
        f"{notice_html}"
        f"<div id=\"lectures\">{lecture_section(library, watch, hold)}</div>"
        "<script>setInterval(function(){fetch('/list').then(function(r){return r.text()}).then(function(t){document.getElementById('lectures').innerHTML=t})},5000)</script>"
        "</body></html>"
    )


def read_product(library: Path, sha: str, name: str) -> bytes:
    if not _SHA.fullmatch(sha) or name not in PRODUCTS:
        raise PermissionError(name)
    root = (library / sha).resolve()
    target = (root / name).resolve()
    if target != root and root not in target.parents:
        raise PermissionError(name)
    if not target.is_file():
        raise FileNotFoundError(name)
    return target.read_bytes()


def apply_hold_action(action: str, hold: Path, job: Job | None = None, library: Path | None = None) -> None:
    if action == "stop":
        hold.parent.mkdir(parents=True, exist_ok=True)
        hold.write_text("{}\n", encoding="utf-8")
        return
    if action == "resume":
        targets = [job] if job is not None else _stopped_jobs(library)
        if not targets:
            hold.unlink(missing_ok=True)
            return
        for item in targets:
            resume(hold, item)


def ollama_answers() -> bool:
    try:
        with urllib.request.urlopen("http://127.0.0.1:11435/api/version", timeout=0.3) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def _stopped_jobs(library: Path | None) -> list[Job]:
    if library is None or not library.is_dir():
        return []
    found = []
    for directory in library.iterdir():
        if not directory.is_dir():
            continue
        job = Job(directory)
        if job.state_path.is_file() and job.load_state().status == "stopped":
            found.append(job)
    return found


def _assign(text: str, key: str, value: str) -> str:
    line = f'{key} = "{value}"'
    lines = []
    found = False
    for current in text.splitlines():
        if current.startswith(f"{key} " ) or current.startswith(f"{key}="):
            lines.append(line)
            found = True
        else:
            lines.append(current)
    if not found:
        lines.append(line)
    return "\n".join(lines) + "\n"


def _json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


class StudyHandler(BaseHTTPRequestHandler):
    library = Path(".")
    watch = Path(".")
    draft_watch: Path | None = None
    draft_library: Path | None = None
    hold = Path("hold.json")
    config: Path | None = None
    notice = ""
    ollama_up = False
    picker = staticmethod(pick_directory)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/list":
            self._send(200, lecture_section(self.library, self.watch, self.hold).encode("utf-8"), "text/html; charset=utf-8")
            return
        if parsed.path == "/":
            body = render_page(
                self.library,
                ollama_up=ollama_answers(),
                watch=self.watch,
                notice=self.notice,
                hold=self.hold,
            ).encode("utf-8")
            self._send(200, body, "text/html; charset=utf-8")
            return
        parts = [unquote(part) for part in parsed.path.split("/") if part]
        if len(parts) == 3 and parts[0] == "files":
            try:
                body = read_product(self.library, parts[1], parts[2])
            except (PermissionError, FileNotFoundError):
                self._send(404, b"", "text/plain")
                return
            self._send(200, body, "text/plain; charset=utf-8")
            return
        self._send(404, b"", "text/plain")

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        fields = parse_qs(self.rfile.read(length).decode("utf-8"))
        parsed = urlparse(self.path)
        if parsed.path == "/pick":
            which = fields.get("which", [""])[0]
            if which == "watch":
                current = self.watch
                title = "Audio folder"
            elif which == "library":
                current = self.library
                title = "Results folder"
            else:
                self._redirect()
                return
            apply_picked(which, self.picker(title, current))
            self._redirect()
            return
        if parsed.path == "/paths":
            if self.config is None:
                StudyHandler.notice = "Configuration is not available."
            else:
                choose_folders(self.config, Path(fields.get("watch", [""])[0]), Path(fields.get("library", [""])[0]))
            self._redirect()
            return
        action = fields.get("action", [""])[0]
        job_id = fields.get("job", [""])[0]
        job = None
        if _SHA.fullmatch(job_id):
            candidate = Job(self.library / job_id)
            if candidate.state_path.is_file():
                job = candidate
        if job is None:
            apply_hold_action(action, self.hold, library=self.library)
        else:
            apply_hold_action(action, self.hold, job)
        self._redirect()

    def _redirect(self) -> None:
        self._send(303, b"", "text/plain")
        self.send_header("Location", "/")
        self.end_headers()

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if status != 303:
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        return
