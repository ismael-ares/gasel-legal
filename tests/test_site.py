from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import check_site
from scripts import render_site


class LegalSiteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.site = Path(self.temp.name) / "site"
        shutil.copytree(ROOT, self.site, ignore=shutil.ignore_patterns(".git", "__pycache__"))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def errors(self) -> list[str]:
        return check_site.validate(self.site)

    def test_complete_site_passes_without_network(self) -> None:
        self.assertEqual([], self.errors())

    def test_missing_page_is_reported(self) -> None:
        (self.site / "legal-ja.html").unlink()
        self.assertTrue(any("legal-ja.html is missing" in error for error in self.errors()))

    def test_broken_local_href_is_reported(self) -> None:
        path = self.site / "privacy.html"
        html = path.read_text(encoding="utf-8").replace('href="legal.html"', 'href="missing.html"', 1)
        path.write_text(html, encoding="utf-8")
        self.assertTrue(any("broken local link: missing.html" in error for error in self.errors()))

    def test_wrong_locale_is_reported(self) -> None:
        path = self.site / "privacy-ja.html"
        html = path.read_text(encoding="utf-8").replace('<html lang="ja-JP">', '<html lang="en-GB">', 1)
        path.write_text(html, encoding="utf-8")
        self.assertTrue(any("privacy-ja.html has the wrong html lang" in error for error in self.errors()))

    def test_truncated_license_is_reported(self) -> None:
        path = self.site / "licenses-ja.html"
        html = path.read_text(encoding="utf-8").replace("TERMINATION", "", 1)
        path.write_text(html, encoding="utf-8")
        errors = self.errors()
        self.assertTrue(any("complete source license" in error for error in errors))

    def test_page_diverged_from_imported_content_is_reported(self) -> None:
        path = self.site / "privacy.html"
        html = path.read_text(encoding="utf-8").replace("Política de privacidad", "Política modificada", 1)
        path.write_text(html, encoding="utf-8")
        self.assertTrue(any("deterministic template/content render" in error for error in self.errors()))

    def test_renderer_escapes_imported_content(self) -> None:
        content = json.loads((ROOT / "content.json").read_text(encoding="utf-8"))
        content["locales"]["es"]["documents"]["privacy"]["summary"] = '<script>alert("x")</script> &'
        license_text = (ROOT / "licenses/google-sans-flex.txt").read_text(encoding="utf-8")
        page = render_site.render_document(content, "es", "privacy", license_text)
        self.assertIn("&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp;", page)
        self.assertNotIn('<script>alert("x")</script>', page)

    def test_render_is_deterministic(self) -> None:
        content = json.loads((ROOT / "content.json").read_text(encoding="utf-8"))
        first = render_site.expected_files(content, ROOT / "licenses/google-sans-flex.txt")
        second = render_site.expected_files(content, ROOT / "licenses/google-sans-flex.txt")
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
