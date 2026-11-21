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
        # Real Spanish catalog fixture plus RTL clones exercise generation without
        # coupling this repository's tests to a sibling Android checkout.
        content = json.loads((ROOT / "tests/fixtures/content.json").read_text(encoding="utf-8"))
        content["registry"] = json.loads((ROOT / "content.json").read_text(encoding="utf-8"))["registry"]
        for locale, tag in (("ar", "ar-MA"), ("ur", "ur-PK")):
            content["locales"][locale] = dict(content["locales"]["es"], tag=tag, language_name=locale, direction="rtl")
            content["language_order"].append(locale)
        for locale, tag, native in (("oc-aranes", "oc-ES-aranes", "Aranés"), ("ca-valencia", "ca-ES-valencia", "Valencià"), ("sr-cyrl", "sr-Cyrl-RS", "Српски")):
            content["locales"][locale] = dict(content["locales"]["es"], tag=tag, language_name=native, direction="ltr")
            content["language_order"].append(locale)
        (self.site / "content.json").write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        license_paths = {name: self.site / "licenses" / name for name in render_site.asset_files(content)}
        for name, markup in render_site.expected_files(content, license_paths).items():
            (self.site / name).write_text(markup, encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def errors(self) -> list[str]:
        return check_site.validate(self.site)

    def test_complete_site_passes_without_network(self) -> None:
        self.assertEqual([], self.errors())

    def test_missing_page_is_reported(self) -> None:
        (self.site / "legal-ar.html").unlink()
        self.assertTrue(any("legal-ar.html is missing" in error for error in self.errors()))

    def test_broken_local_href_is_reported(self) -> None:
        path = self.site / "privacy.html"
        html = path.read_text(encoding="utf-8").replace('href="#legal"', 'href="missing.html"', 1)
        path.write_text(html, encoding="utf-8")
        self.assertTrue(any("broken local link: missing.html" in error for error in self.errors()))

    def test_wrong_locale_is_reported(self) -> None:
        path = self.site / "privacy-ar.html"
        html = path.read_text(encoding="utf-8").replace('<html lang="ar-MA" dir="rtl">', '<html lang="en-GB">', 1)
        path.write_text(html, encoding="utf-8")
        self.assertTrue(any("privacy-ar.html has the wrong html lang" in error for error in self.errors()))

    def test_rtl_pages_use_rtl_and_license_remains_ltr(self) -> None:
        for locale in ("ar", "ur"):
            privacy = check_site.parse_page(self.site / f"privacy-{locale}.html")
            self.assertEqual("rtl", privacy.html_dir)
            self.assertEqual("ltr", privacy.license_dir)

    def test_language_menu_uses_short_codes_and_keeps_full_tags_in_attributes(self) -> None:
        page = (self.site / "privacy.html").read_text(encoding="utf-8")
        for code, tag, native in (("OC", "oc-ES-aranes", "Aranés"), ("CA", "ca-ES-valencia", "Valencià"), ("SR", "sr-Cyrl-RS", "Српски")):
            self.assertIn(f'lang="{tag}" hreflang="{tag}" data-locale="{tag}"', page)
            self.assertIn(f'<span class="li-code">{code}</span><span class="li-name">{native}</span>', page)
        css = (self.site / "styles.css").read_text(encoding="utf-8")
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr));", css)
        self.assertRegex(css, r"\.lang-item\s*\{[^}]*min-width:\s*0")
        self.assertRegex(css, r"\.li-name\s*\{[^}]*text-overflow:\s*ellipsis")
        self.assertIn("grid-template-columns: 1fr;", css)  # Mobile bottom sheet remains one column.
        for locale in ("ar", "ur"):
            rtl = (self.site / f"privacy-{locale}.html").read_text(encoding="utf-8")
            self.assertIn('dir="rtl"', rtl)
            self.assertIn('class="lang-list"', rtl)

    def test_pages_use_custom_domain_canonical_and_language_alternates(self) -> None:
        for name, locale in (("privacy.html", "es"), ("privacy-ar.html", "ar"), ("licenses-ar.html", "ar")):
            markup = (self.site / name).read_text(encoding="utf-8")
            canonical = f'https://gasel.yvel.uk/privacy{"-" + locale if locale != "es" else ""}.html'
            self.assertIn(f'<link rel="canonical" href="{canonical}">', markup)
            self.assertIn('hreflang="x-default" href="https://gasel.yvel.uk/privacy.html"', markup)
            self.assertNotIn("ismael-ares.github.io", markup)

    def test_truncated_license_is_reported(self) -> None:
        path = self.site / "privacy.html"
        html = path.read_text(encoding="utf-8").replace("TERMINATION", "", 1)
        path.write_text(html, encoding="utf-8")
        errors = self.errors()
        self.assertTrue(any("complete source license" in error for error in errors))

    def test_page_diverged_from_imported_content_is_reported(self) -> None:
        path = self.site / "privacy.html"
        content = json.loads((self.site / "content.json").read_text(encoding="utf-8"))
        heading = content["locales"]["es"]["strings"]["legal_hero_title"]
        html = path.read_text(encoding="utf-8").replace(heading, "Política modificada", 1)
        path.write_text(html, encoding="utf-8")
        self.assertTrue(any("deterministic template/content render" in error for error in self.errors()))

    def test_renderer_escapes_imported_content(self) -> None:
        content = json.loads((self.site / "content.json").read_text(encoding="utf-8"))
        content["locales"]["es"]["strings"]["legal_hero_promise"] = '<script>alert("x")</script> &'
        licenses = {name: (self.site / "licenses" / name).read_text(encoding="utf-8") for name in render_site.asset_files(content)}
        page = render_site.render_document(content, "es", "privacy", licenses)
        self.assertIn("&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp;", page)
        self.assertNotIn('<script>alert("x")</script>', page)

    def test_render_is_deterministic(self) -> None:
        content = json.loads((self.site / "content.json").read_text(encoding="utf-8"))
        paths = {name: self.site / "licenses" / name for name in render_site.asset_files(content)}
        first = render_site.expected_files(content, paths)
        second = render_site.expected_files(content, paths)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
