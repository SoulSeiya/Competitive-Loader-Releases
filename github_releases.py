"""Public release metadata with a short cache and a web fallback for API limits.

No credentials are needed or stored. A web result must identify a real release
and its uploaded assets; download URLs and hashes are not guessed.
"""
import json
import math
from html.parser import HTMLParser
from pathlib import Path
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

TTL = 300
LOCK = threading.RLock()
TAG = re.compile(r"v?\d+(?:\.\d+){1,3}")
DIGEST = re.compile(r"sha256:[0-9a-fA-F]{64}")


def number(value, default=0):
    try:
        value = float(value)
        return value if math.isfinite(value) else default
    except (ValueError, TypeError):
        return default


class ReleasePage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.notes = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div":
            if self.depth:
                self.depth += 1
            elif "markdown-body" in attrs.get("class", "").split():
                self.depth = 1
        if self.depth and tag in ("p", "li", "br", "h1", "h2", "h3"):
            self.notes.append("\n")

    def handle_endtag(self, tag):
        if tag == "div" and self.depth:
            self.depth -= 1

    def handle_data(self, data):
        if self.depth:
            self.notes.append(data)


class AssetsPage(HTMLParser):
    def __init__(self, repo, tag):
        super().__init__()
        self.prefix = f"/{repo}/releases/download/{tag}/"
        self.assets = []
        self.depth = 0
        self.row = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "li":
            if not self.depth:
                self.row = {}
            self.depth += 1
        if not self.depth:
            return
        if tag == "a":
            url = urllib.parse.urljoin("https://github.com", attrs.get("href", ""))
            parsed = urllib.parse.urlsplit(url)
            if (parsed.scheme == "https" and parsed.netloc == "github.com" and
                    parsed.path.startswith(self.prefix)):
                name = urllib.parse.unquote(parsed.path[len(self.prefix):])
                if name and "/" not in name and "\\" not in name:
                    self.row.update(name=name, browser_download_url=url, size=0)
        if tag == "clipboard-copy" and DIGEST.fullmatch(attrs.get("value", "")):
            self.row["digest"] = attrs["value"].lower()
        if tag == "relative-time":
            self.row["updated_at"] = attrs.get("datetime", "")

    def handle_endtag(self, tag):
        if tag == "li" and self.depth:
            self.depth -= 1
            if not self.depth and self.row.get("name"):
                self.row["id"] = "web:" + self.row["browser_download_url"] + ":" + self.row.get("digest", "")
                self.assets.append(self.row)


def _read(response):
    data = response.read(4 * 1024 * 1024 + 1)
    if len(data) > 4 * 1024 * 1024:
        raise ValueError("Respuesta de versiones demasiado grande")
    return data.decode("utf-8")


def _web_release(repo, tag, agent):
    base = f"https://github.com/{repo}/releases/"
    url = base + ("tag/" + tag if tag else "latest")
    headers = {"User-Agent": agent, "Accept": "text/html"}
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=15) as response:
        resolved = urllib.parse.urlsplit(response.geturl())
        prefix = f"/{repo}/releases/tag/"
        if resolved.scheme != "https" or resolved.netloc != "github.com" or not resolved.path.startswith(prefix):
            raise ValueError("GitHub no devolvió una publicación verificable")
        actual_tag = urllib.parse.unquote(resolved.path[len(prefix):])
        if not TAG.fullmatch(actual_tag) or (tag and actual_tag != tag):
            raise ValueError("Etiqueta de publicación no válida")
        page = ReleasePage()
        page.feed(_read(response))
    url = base + "expanded_assets/" + actual_tag
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=15) as response:
        assets = AssetsPage(repo, actual_tag)
        assets.feed(_read(response))
    notes = "\n".join(line.strip() for line in "".join(page.notes).splitlines() if line.strip())[:12000]
    return {"tag_name": actual_tag, "name": actual_tag, "body": notes,
            "assets": assets.assets, "metadata_source": "web"}


def release_metadata(repo, tag, cache_path, agent):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) or (tag and not TAG.fullmatch(tag)):
        raise ValueError("Repositorio o etiqueta no válidos")
    with LOCK:
        cache_path = Path(cache_path)
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            if not isinstance(cache, dict):
                cache = {}
        except (OSError, ValueError):
            cache = {}
        key = repo + ":" + (tag or "latest")
        now = time.time()
        entry = cache.get(key, {})
        if isinstance(entry, dict) and 0 <= now - number(entry.get("at")) < TTL and isinstance(entry.get("release"), dict):
            return entry["release"]
        result = None
        if now >= number(cache.get("api_retry_at")):
            endpoint = "tags/" + tag if tag else "latest"
            request = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/{endpoint}",
                headers={"User-Agent": agent, "Accept": "application/vnd.github+json",
                         "X-GitHub-Api-Version": "2022-11-28"})
            try:
                with urllib.request.urlopen(request, timeout=12) as response:
                    result = json.loads(_read(response))
                    if not isinstance(result, dict) or not result.get("tag_name"):
                        raise ValueError("Respuesta de versiones no válida")
            except urllib.error.HTTPError as exc:
                if exc.code not in (403, 429) and exc.code < 500:
                    raise
                if exc.code in (403, 429):
                    headers = exc.headers or {}
                    reset = max(number(headers.get("X-RateLimit-Reset")),
                                now + number(headers.get("Retry-After"), 300))
                    cache["api_retry_at"] = min(now + 86400, max(now + 60, reset))
                exc.close()
            except (OSError, ValueError, urllib.error.URLError):
                result = None
        try:
            if result is None:
                print("[VERSIONES] API no disponible; consultando la página pública de Releases.")
                result = _web_release(repo, tag, agent)
            cache[key] = {"at": now, "release": result}
            return result
        finally:
            # Persist cooldown even if the web request also fails. It is shared
            # by decomp/Loader lookups and survives restarting the application.
            try:
                temp = cache_path.with_suffix(".tmp")
                temp.write_text(json.dumps(cache), encoding="utf-8")
                temp.replace(cache_path)
            except OSError:
                pass
