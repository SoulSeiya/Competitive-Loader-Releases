import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import urllib.error

import github_releases as releases


REPO = "SoulSeiya/Competitive-Loader-Releases"
TAG = "v1.5.8"
DIGEST = "sha256:" + "a" * 64
ZIP = "CompetitiveLoader-windows-x64.zip"


class Response(io.BytesIO):
    def __init__(self, data, url):
        super().__init__(data.encode())
        self.url = url

    def geturl(self):
        return self.url


class GithubReleaseTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.cache = Path(folder.name) / "cache.json"
        self.calls = []

    def web(self, req, **kwargs):
        url = req.full_url
        self.calls.append(url)
        if url.startswith("https://api.github.com/"):
            raise urllib.error.HTTPError(url, 403, "rate limit exceeded",
                                         {"X-RateLimit-Reset": "5000"}, None)
        if "/expanded_assets/" in url:
            return Response(f'''<ul><li><a href="/{REPO}/releases/download/{TAG}/{ZIP}">{ZIP}</a>
                <clipboard-copy value="{DIGEST}"></clipboard-copy>
                <relative-time datetime="2026-10-15T00:00:00Z"></relative-time></li>
                <li><a href="/{REPO}/archive/refs/tags/{TAG}.zip">Source</a></li></ul>''', url)
        return Response('<div class="markdown-body"><p>Mejoras</p><ul><li>Actualizador corregido</li></ul></div>',
                        f"https://github.com/{REPO}/releases/tag/{TAG}")

    def test_rate_limit_uses_public_release_and_preserves_asset_digest(self):
        with (mock.patch.object(releases.time, "time", return_value=1000),
              mock.patch.object(releases.urllib.request, "urlopen", side_effect=self.web)):
            result = releases.release_metadata(REPO, None, self.cache, "test")
        self.assertEqual(result["tag_name"], TAG)
        self.assertEqual(result["metadata_source"], "web")
        self.assertIn("Actualizador corregido", result["body"])
        self.assertEqual(len(result["assets"]), 1)
        self.assertEqual(result["assets"][0]["digest"], DIGEST)
        self.assertEqual(result["assets"][0]["browser_download_url"],
                         f"https://github.com/{REPO}/releases/download/{TAG}/{ZIP}")

    def test_cache_and_shared_cooldown_survive_a_second_lookup(self):
        with (mock.patch.object(releases.time, "time", return_value=1000),
              mock.patch.object(releases.urllib.request, "urlopen", side_effect=self.web)):
            first = releases.release_metadata(REPO, None, self.cache, "test")
            count = len(self.calls)
            self.assertEqual(releases.release_metadata(REPO, None, self.cache, "test"), first)
            self.assertEqual(len(self.calls), count)
        with (mock.patch.object(releases.time, "time", return_value=1400),
              mock.patch.object(releases.urllib.request, "urlopen", side_effect=self.web)):
            releases.release_metadata(REPO, TAG, self.cache, "test")
        self.assertEqual(sum(url.startswith("https://api.github.com/") for url in self.calls), 1)

    def test_expired_cache_is_refreshed_without_reporting_stale_data_as_current(self):
        self.cache.write_text(json.dumps({REPO + ":latest": {"at": 1, "release": {"tag_name": "v1.0.0"}}}))
        with (mock.patch.object(releases.time, "time", return_value=1000),
              mock.patch.object(releases.urllib.request, "urlopen", side_effect=self.web)):
            result = releases.release_metadata(REPO, None, self.cache, "test")
        self.assertEqual(result["tag_name"], TAG)

    def test_rate_cooldown_is_saved_even_when_web_is_unavailable(self):
        def fail(req, **kw):
            if req.full_url.startswith("https://api.github.com/"):
                raise urllib.error.HTTPError(req.full_url, 429, "limited", {"Retry-After": "900"}, None)
            raise urllib.error.URLError("offline")
        with (mock.patch.object(releases.time, "time", return_value=1000),
              mock.patch.object(releases.urllib.request, "urlopen", side_effect=fail)):
            with self.assertRaises(urllib.error.URLError):
                releases.release_metadata(REPO, None, self.cache, "test")
        self.assertEqual(json.loads(self.cache.read_text())["api_retry_at"], 1900)

    def test_redirect_to_another_repository_is_rejected(self):
        def wrong(req, **kw):
            if req.full_url.startswith("https://api.github.com/"):
                raise urllib.error.HTTPError(req.full_url, 403, "limited", {}, None)
            return Response("", "https://github.com/other/project/releases/tag/v1.5.8")
        with mock.patch.object(releases.urllib.request, "urlopen", side_effect=wrong):
            with self.assertRaisesRegex(ValueError, "verificable"):
                releases.release_metadata(REPO, None, self.cache, "test")

    def test_assets_from_other_repositories_are_ignored(self):
        parser = releases.AssetsPage(REPO, TAG)
        parser.feed('<li><a href="https://evil.invalid/payload.zip">zip</a></li>')
        self.assertEqual(parser.assets, [])

    def test_invalid_api_json_shape_uses_web_instead_of_caching_bad_metadata(self):
        def invalid(req, **kwargs):
            if req.full_url.startswith("https://api.github.com/"):
                return Response("[]", req.full_url)
            return self.web(req, **kwargs)
        with mock.patch.object(releases.urllib.request, "urlopen", side_effect=invalid):
            result = releases.release_metadata(REPO, None, self.cache, "test")
        self.assertEqual(result["metadata_source"], "web")
        self.assertEqual(result["tag_name"], TAG)


if __name__ == "__main__":
    unittest.main()
