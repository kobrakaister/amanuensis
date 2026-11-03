"""Download one long English lecture from MIT OpenCourseWare.

Starts from the public OCW search, opens the course pages, and follows the links
to the video and the transcript. It does not score the audio and does not call
the local transcription service.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

USER_AGENT = "mba-lecture-study/0.1 (local transcription test; educational)"
PAUSE_SECONDS = 2.0
OCW = "https://ocw.mit.edu"
SEARCH = "https://open.mit.edu/api/v0/search/"
PREFERRED_SECONDS = 75 * 60
FALLBACK_SECONDS = 50 * 60
MAX_LECTURE_SECONDS = 6 * 3600
MIN_BITS_PER_SECOND = 24_000
SKIP = (
    "recitation",
    "problem session",
    "problem-session",
    "tutorial",
    "office hour",
    "office-hour",
    "trailer",
    "interview",
    "instructor insight",
    "insight",
)
ROMAN = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}


@dataclass(frozen=True)
class Course:
    title: str
    slug: str
    year: int

    @property
    def url(self) -> str:
        return f"{OCW}/{self.slug.strip('/')}/"


@dataclass(frozen=True)
class Link:
    url: str
    text: str


@dataclass
class Video:
    download: str
    transcript: str | None
    tracks: list[tuple[str, str]]


@dataclass(frozen=True)
class MediaFile:
    name: str
    title: str
    seconds: float


@dataclass(frozen=True)
class Choice:
    course: str
    lecture: str
    page_url: str
    media_url: str
    seconds: float
    transcript_url: str
    transcript_kind: str


class Client:
    def __init__(self) -> None:
        self._last = 0.0
        self._pages: dict[str, str] = {}

    def _pause(self) -> None:
        if self._last:
            wait = PAUSE_SECONDS - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
        self._last = time.monotonic()

    def _request(self, url: str, *, data: bytes | None = None, accept: str) -> bytes:
        if not allowed(url):
            raise RuntimeError(f"host non previsto: {url}")
        self._pause()
        request = urllib.request.Request(
            url,
            data=data,
            headers={"User-Agent": USER_AGENT, "Accept": accept},
            method="POST" if data is not None else "GET",
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            return response.read()

    def text(self, url: str) -> str:
        cached = self._pages.get(url)
        if cached is not None:
            return cached
        body = self._request(url, accept="text/html,application/json").decode("utf-8", "replace")
        self._pages[url] = body
        return body

    def post_json(self, url: str, body: dict) -> dict:
        if not allowed(url):
            raise RuntimeError(f"host non previsto: {url}")
        self._pause()
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode(),
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode())

    def save(self, url: str, dest: Path) -> None:
        if dest.exists() and dest.stat().st_size > 0:
            print(f"already present: {dest}", flush=True)
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        partial = dest.with_suffix(dest.suffix + ".part")
        if not allowed(url):
            raise RuntimeError(f"host non previsto: {url}")
        self._pause()
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=180) as response, partial.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
        partial.replace(dest)


def allowed(url: str) -> bool:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    return host in {"ocw.mit.edu", "open.mit.edu", "archive.org", "www.archive.org"} or host.endswith(
        ".archive.org"
    )


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[Link] = []
        self.videos: list[Video] = []
        self.og_title = ""
        self._href: str | None = None
        self._text: list[str] = []
        self._video: Video | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag == "a":
            self._href = values.get("href")
            self._text = []
        elif tag == "video":
            self._video = Video(values.get("data-downloadlink", ""), values.get("data-transcriptlink") or None, [])
            self.videos.append(self._video)
        elif tag == "track" and self._video is not None:
            self._video.tracks.append((values.get("srclang", ""), values.get("src", "")))
        elif tag == "meta" and values.get("property") == "og:title":
            self.og_title = values.get("content", "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            self.links.append(Link(self._href, " ".join(self._text).strip()))
            self._href = None
        elif tag == "video":
            self._video = None

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)


def parse_page(html: str) -> PageParser:
    parser = PageParser()
    parser.feed(html)
    return parser


def lecture_title(og_title: str, fallback: str) -> str:
    part = og_title.split("|", 1)[0].strip()
    return part or fallback.strip() or "Lezione"


def skipped(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in SKIP)


def interesting(link: Link) -> bool:
    blob = f"{link.url} {link.text}".lower()
    if skipped(blob) or "lecture-note" in blob or "lecture notes" in blob:
        return False
    if any(word in blob for word in ("slides", "(pdf)", ".pdf")):
        return False
    path = urllib.parse.urlparse(link.url).path.rstrip("/").split("/")[-1].lower()
    if "video-lecture" in link.url or "lecture-video" in link.url:
        return True
    if "video_galleries" in link.url and "lecture" in link.url:
        return True
    if "/resources/" in link.url and "lecture" in path:
        return True
    if path.startswith("lecture"):
        return True
    return link.text.lower().startswith("lecture")


def same_course(url: str, slug: str) -> bool:
    path = urllib.parse.urlparse(url).path
    return path.startswith("/" + slug.strip("/") + "/") or path.rstrip("/") == "/" + slug.strip("/")


def absolute(page_url: str, href: str) -> str:
    return urllib.parse.urljoin(page_url, href)


def dedupe(links: list[Link]) -> list[Link]:
    seen: set[str] = set()
    result: list[Link] = []
    for link in links:
        if link.url in seen or not link.text:
            continue
        seen.add(link.url)
        result.append(link)
    return result


def without_parents(links: list[Link]) -> list[Link]:
    paths = [urllib.parse.urlparse(link.url).path.rstrip("/") for link in links]
    kept: list[Link] = []
    for link, path in zip(links, paths):
        if any(other != path and other.startswith(path + "/") for other in paths):
            continue
        kept.append(link)
    return kept


def entry_points(html: str, page_url: str, slug: str) -> list[Link]:
    parsed = parse_page(html)
    links = []
    for link in parsed.links:
        url = absolute(page_url, link.url)
        if urllib.parse.urlparse(url).hostname != "ocw.mit.edu":
            continue
        if not same_course(url, slug):
            continue
        links.append(Link(url, link.text))
    galleries = [
        link
        for link in links
        if "video_galleries" in link.url and "lecture" in link.url.lower() and "insight" not in link.url.lower()
    ]
    if galleries:
        return dedupe(galleries)[:1]
    selected = [link for link in links if interesting(link)]
    return without_parents(dedupe(selected))


def resource_links(html: str, page_url: str, slug: str) -> list[Link]:
    parsed = parse_page(html)
    found: list[Link] = []
    for link in parsed.links:
        url = absolute(page_url, link.url)
        if urllib.parse.urlparse(url).hostname != "ocw.mit.edu" or not same_course(url, slug):
            continue
        if "/resources/" not in url or skipped(f"{url} {link.text}"):
            continue
        blob = f"{url} {link.text}".lower()
        if any(word in blob for word in ("slides", "(pdf)", ".pdf", "lecture-note")):
            continue
        found.append(Link(url, link.text))
    return dedupe(found)


def english_transcript(video: Video, page_url: str) -> tuple[str, str] | None:
    tracks = []
    for language, src in video.tracks:
        if src and language.lower().startswith("en"):
            kind = "srt" if src.lower().split("?", 1)[0].endswith(".srt") else "vtt"
            tracks.append((0 if kind == "vtt" else 1, absolute(page_url, src), kind))
    if tracks:
        tracks.sort()
        _, url, kind = tracks[0]
        return url, kind
    if video.transcript:
        url = absolute(page_url, video.transcript)
        kind = "srt" if url.lower().split("?", 1)[0].endswith(".srt") else "pdf"
        if url.lower().split("?", 1)[0].endswith(".vtt"):
            kind = "vtt"
        return url, kind
    return None


def videos_on(html: str, page_url: str) -> tuple[str, list[tuple[Video, tuple[str, str]]]]:
    parsed = parse_page(html)
    ready: list[tuple[Video, tuple[str, str]]] = []
    for video in parsed.videos:
        if not video.download:
            continue
        transcript = english_transcript(video, page_url)
        if transcript is None:
            continue
        video.download = absolute(page_url, video.download)
        ready.append((video, transcript))
    return lecture_title(parsed.og_title, ""), ready


def basename(url: str) -> str:
    path = urllib.parse.urlparse(url).path
    return urllib.parse.unquote(path.rstrip("/").split("/")[-1])


def archive_item(url: str) -> str | None:
    match = re.search(r"archive\.org/download/([^/]+)/", url, re.IGNORECASE)
    return match.group(1) if match else None


def archive_files(client: Client, item: str) -> list[MediaFile]:
    raw = client.text(f"https://archive.org/metadata/{urllib.parse.quote(item)}")
    data = json.loads(raw)
    files: list[MediaFile] = []
    for entry in data.get("files", []):
        name = str(entry.get("name") or "")
        if not name.lower().endswith(".mp4") or ".ia." in name.lower() or not entry.get("length"):
            continue
        try:
            seconds = float(entry["length"])
            size = int(entry["size"]) if str(entry.get("size") or "").isdigit() else 0
        except (TypeError, ValueError):
            continue
        if seconds <= 0 or seconds > MAX_LECTURE_SECONDS:
            continue
        if size and size * 8 / seconds < MIN_BITS_PER_SECOND:
            continue
        title = str(entry.get("title") or name)
        if skipped(f"{title} {name}"):
            continue
        files.append(MediaFile(name.split("/")[-1], title, seconds))
    files.sort(key=lambda item: item.seconds, reverse=True)
    return files


def tokens(text: str) -> set[str]:
    cleaned = text.lower().replace("_", " ")
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    drop = {"the", "a", "an", "of", "and", "part", "video", "mp4", "pdf", "slides", "lecture"}
    return {token for token in cleaned.split() if token and token not in drop}


def title_score(link_text: str, media: MediaFile) -> float:
    left = tokens(link_text)
    right = tokens(f"{media.title} {media.name}")
    if not left or not right:
        return 0.0
    romans = {token for token in left if token in ROMAN}
    if romans and not romans <= right:
        return 0.0
    return len(left & right) / len(left)


def probe_seconds(url: str) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return None
    time.sleep(PAUSE_SECONDS)
    completed = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", url],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    try:
        return float(completed.stdout.strip())
    except ValueError:
        return None


def format_duration(seconds: float) -> str:
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^A-Za-z0-9]+", "-", normalized).strip("-").lower()
    return slug[:80] or "lecture"


def courses(client: Client) -> list[Course]:
    found: list[Course] = []
    start = 0
    while True:
        payload = client.post_json(
            SEARCH,
            {
                "from": start,
                "size": 50,
                "_source": ["title", "runs.slug", "runs.year"],
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"object_type": "course"}},
                            {"term": {"offered_by": "OCW"}},
                            {"term": {"course_feature_tags": "Lecture Videos"}},
                        ]
                    }
                },
            },
        )
        hits = payload.get("hits", {}).get("hits", [])
        if not hits:
            break
        for hit in hits:
            source = hit.get("_source", {})
            runs = source.get("runs") or []
            if not runs or not runs[0].get("slug"):
                continue
            found.append(Course(source.get("title") or runs[0]["slug"], runs[0]["slug"], int(runs[0].get("year") or 9999)))
        if len(hits) < 50:
            break
        start += 50
    unique: dict[str, Course] = {}
    for course in found:
        unique.setdefault(course.slug, course)
    return sorted(unique.values(), key=lambda course: (course.year, course.slug))


def first_described_video(client: Client, course: Course, entries: list[Link]) -> tuple[str, str, Video, tuple[str, str]] | None:
    queue = list(entries)
    seen: set[str] = set()
    while queue:
        link = queue.pop(0)
        if link.url in seen:
            continue
        seen.add(link.url)
        html = client.text(link.url)
        _title, ready = videos_on(html, link.url)
        if ready:
            video, transcript = ready[0]
            return link.url, lecture_title(_title, link.text), video, transcript
        if "/resources/" not in urllib.parse.urlparse(link.url).path:
            extra = resource_links(html, link.url, course.slug)
            if not extra:
                extra = [
                    item
                    for item in entry_points(html, link.url, course.slug)
                    if item.url not in seen and "video_galleries" not in item.url
                ]
            queue[0:0] = extra
    return None


def expand_resources(client: Client, course: Course, entries: list[Link]) -> list[Link]:
    resources: list[Link] = []
    for link in entries:
        if "/resources/" in urllib.parse.urlparse(link.url).path:
            resources.append(link)
            continue
        html = client.text(link.url)
        found = resource_links(html, link.url, course.slug)
        resources.extend(found or entry_points(html, link.url, course.slug))
    return dedupe(resources)


def choice_from_page(course: Course, page_url: str, lecture: str, video: Video, transcript: tuple[str, str], seconds: float) -> Choice:
    transcript_url, kind = transcript
    return Choice(course.title, lecture, page_url, video.download, seconds, transcript_url, kind)


def resolve_archive_file(client: Client, course: Course, resources: list[Link], media: MediaFile) -> Choice | None:
    ranked = sorted(resources, key=lambda link: title_score(link.text, media), reverse=True)
    for link in ranked:
        if title_score(link.text, media) <= 0 and link is not ranked[0]:
            continue
        html = client.text(link.url)
        title, ready = videos_on(html, link.url)
        for video, transcript in ready:
            if basename(video.download) == media.name:
                return choice_from_page(course, link.url, lecture_title(title, link.text), video, transcript, media.seconds)
        if title_score(link.text, media) < 0.34:
            break
    for link in resources:
        html = client.text(link.url)
        title, ready = videos_on(html, link.url)
        for video, transcript in ready:
            if basename(video.download) == media.name:
                return choice_from_page(course, link.url, lecture_title(title, link.text), video, transcript, media.seconds)
    return None


def files_at_least(files: list[MediaFile], minimum: float) -> list[MediaFile]:
    return [item for item in files if item.seconds >= minimum]


@dataclass
class Fallback:
    seconds: float
    course: Course
    entries: list[Link]
    media: MediaFile | None = None
    choice: Choice | None = None


def remember(best: Fallback | None, seconds: float, course: Course, entries: list[Link], media: MediaFile | None, choice: Choice | None) -> Fallback | None:
    if seconds <= FALLBACK_SECONDS:
        return best
    if best is not None and seconds <= best.seconds:
        return best
    return Fallback(seconds, course, entries, media, choice)


def examine(client: Client, course: Course, best: Fallback | None) -> tuple[Choice | None, Fallback | None]:
    print(f"checking {course.title} ({course.year})", file=sys.stderr, flush=True)
    try:
        html = client.text(course.url)
    except urllib.error.HTTPError as exc:
        print(f"  page unavailable: {exc.code}", file=sys.stderr, flush=True)
        return None, best
    entries = entry_points(html, course.url, course.slug)
    if not entries:
        print("  no lecture page", file=sys.stderr, flush=True)
        return None, best
    if "video_galleries" in entries[0].url:
        gallery = client.text(entries[0].url)
        resources = resource_links(gallery, entries[0].url, course.slug)
        entries = resources or entry_points(gallery, entries[0].url, course.slug)
    described = first_described_video(client, course, entries)
    if described is None:
        print("  no video with an English transcript", file=sys.stderr, flush=True)
        return None, best
    page_url, lecture, video, transcript = described
    item = archive_item(video.download)
    if item is not None:
        files = archive_files(client, item)
        for media in files_at_least(files, PREFERRED_SECONDS):
            resources = expand_resources(client, course, entries)
            chosen = resolve_archive_file(client, course, resources, media)
            if chosen is not None:
                return chosen, best
        over_fifty = [media for media in files if media.seconds > FALLBACK_SECONDS]
        if over_fifty:
            best = remember(best, over_fifty[0].seconds, course, entries, over_fifty[0], None)
        return None, best
    seconds = probe_seconds(video.download)
    if seconds is not None:
        current = choice_from_page(course, page_url, lecture, video, transcript, seconds)
        if seconds >= PREFERRED_SECONDS:
            return current, best
        best = remember(best, seconds, course, entries, None, current)
    for link in entries:
        if link.url == page_url:
            continue
        html = client.text(link.url)
        title, ready = videos_on(html, link.url)
        if not ready:
            continue
        sibling, sibling_transcript = ready[0]
        sibling_seconds = probe_seconds(sibling.download)
        if sibling_seconds is None:
            continue
        candidate = choice_from_page(
            course, link.url, lecture_title(title, link.text), sibling, sibling_transcript, sibling_seconds
        )
        if sibling_seconds >= PREFERRED_SECONDS:
            return candidate, best
        best = remember(best, sibling_seconds, course, entries, None, candidate)
    return None, best


def find_choice(client: Client) -> Choice:
    best: Fallback | None = None
    for course in courses(client):
        chosen, best = examine(client, course, best)
        if chosen is not None:
            return chosen
    if best is None:
        raise SystemExit("No English lecture with a transcript is longer than 50 minutes.")
    if best.choice is not None:
        return best.choice
    assert best.media is not None
    resources = expand_resources(client, best.course, best.entries)
    chosen = resolve_archive_file(client, best.course, resources, best.media)
    if chosen is None:
        raise SystemExit("The longest lecture has no linked English transcript.")
    return chosen


def print_choice(choice: Choice) -> None:
    print(f"Course: {choice.course}", flush=True)
    print(f"Lecture: {choice.lecture}", flush=True)
    print(f"URL: {choice.page_url}", flush=True)
    print(f"Duration: {format_duration(choice.seconds)}", flush=True)
    print(f"Transcript: {choice.transcript_kind}", flush=True)


def extract_audio(video: Path, audio: Path) -> None:
    if audio.exists() and audio.stat().st_size > 0:
        print(f"already present: {audio}", flush=True)
        return
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise SystemExit("ffmpeg is not on PATH")
    partial = audio.with_name("audio.part.wav")
    completed = subprocess.run(
        [ffmpeg, "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(partial)],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0 or not partial.exists():
        partial.unlink(missing_ok=True)
        raise SystemExit(completed.stderr[-2000:] or "ffmpeg did not create the WAV")
    partial.replace(audio)


def audio_seconds(path: Path) -> float:
    seconds = probe_seconds(str(path))
    if seconds is None:
        raise SystemExit(f"ffprobe cannot read the duration of {path}")
    return seconds


def download(choice: Choice, keep_video: bool) -> None:
    folder = Path("data") / "ocw" / slugify(choice.lecture)
    folder.mkdir(parents=True, exist_ok=True)
    video = folder / basename(choice.media_url)
    transcript = folder / f"transcript.{choice.transcript_kind}"
    audio = folder / "audio.wav"
    client = Client()
    print_choice(choice)
    client.save(choice.transcript_url, transcript)
    client.save(choice.media_url, video)
    extract_audio(video, audio)
    if video.exists() and not keep_video:
        video.unlink()
    print("", flush=True)
    print(f"Lecture: {choice.lecture}", flush=True)
    print(f"Audio duration: {format_duration(audio_seconds(audio))}", flush=True)
    print(f"Audio: {audio.resolve()}", flush=True)
    print(f"Transcript ({choice.transcript_kind}): {transcript.resolve()}", flush=True)
    if keep_video:
        print(f"Video: {video.resolve()}", flush=True)
    else:
        print("Video: removed after extracting the audio", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download one long lecture from MIT OpenCourseWare")
    parser.add_argument("--keep-video", action="store_true", help="keep the MP4 after extracting the audio")
    args = parser.parse_args(argv)
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        print("ffmpeg and ffprobe must be on PATH", file=sys.stderr)
        return 1
    try:
        choice = find_choice(Client())
        download(choice, args.keep_video)
    except urllib.error.URLError as exc:
        print(f"request failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
