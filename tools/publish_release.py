"""Publish the already-tested package with the existing Git credential helper.

Credentials stay in memory and are never written into files, arguments or logs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.error
import urllib.parse
import urllib.request

REPOSITORY = "SoulSeiya/Competitive-Loader-Releases"


def headers():
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    credential = subprocess.run(["git", "credential", "fill"],
        input=f"protocol=https\nhost=github.com\npath={REPOSITORY}.git\n\n",
        text=True, capture_output=True, check=True, env=env)
    values = dict(line.split("=", 1) for line in credential.stdout.splitlines() if "=" in line)
    token = values.get("password")
    if not token:
        raise RuntimeError("El ayudante de Git no devolvió una credencial utilizable.")
    return {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "Competitive-Loader-Release"}


def request(url, auth, method="GET", payload=None, content_type="application/json"):
    body = json.dumps(payload).encode() if isinstance(payload, dict) else payload
    req = urllib.request.Request(url, data=body, method=method,
                                 headers=dict(auth, **{"Content-Type": content_type}))
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read()).get("message", exc.reason)
        except (ValueError, UnicodeError):
            detail = exc.reason
        raise RuntimeError(f"GitHub HTTP {exc.code}: {detail}") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--tag")
    parser.add_argument("--commit")
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--notes", type=Path, default=Path("RELEASE-NOTES.md"))
    args = parser.parse_args()
    auth = headers()
    base = "https://api.github.com/repos/" + REPOSITORY
    if args.check:
        repo = request(base, auth)
        print(json.dumps({"repository": repo["full_name"], "permissions": repo.get("permissions")}, indent=2))
        return
    if not args.tag or not args.commit or not args.archive:
        parser.error("Publicar requiere --tag, --commit y --archive")
    package = args.archive.read_bytes()
    release = request(base + "/releases", auth, "POST", {
        "tag_name": args.tag, "target_commitish": args.commit,
        "name": "Competitive Loader " + args.tag, "body": args.notes.read_text(encoding="utf-8"),
        "draft": True, "prerelease": False,
    })
    upload_url = release["upload_url"].split("{", 1)[0]
    asset = request(upload_url + "?" + urllib.parse.urlencode({"name": args.archive.name}),
                    auth, "POST", package, "application/zip")
    digest = hashlib.sha256(package).hexdigest()
    if asset.get("digest") and asset["digest"] != "sha256:" + digest:
        raise RuntimeError("El hash publicado no coincide; la Release permanece como borrador.")
    public = request(base + "/releases/" + str(release["id"]), auth, "PATCH", {"draft": False})
    print(json.dumps({"release": public["html_url"], "asset": asset["browser_download_url"],
                      "sha256": digest}, indent=2))


if __name__ == "__main__":
    main()
