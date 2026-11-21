#!/usr/bin/env python3
"""Validate all legal routes, localized content and bundled assets offline."""
from __future__ import annotations

import hashlib
import html.parser
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit

import scripts.render_site as render_site

ROOT = Path(__file__).resolve().parent
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class PageParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.html_lang = ""
        self.html_dir = "ltr"
        self.title = ""
        self.title_depth = 0
        self.heading: tuple[str, int] | None = None
        self.headings: dict[str, list[str]] = {"h1": [], "h2": [], "h3": []}
        self.mains = 0
        self.articles = 0
        self.stylesheets: list[str] = []
        self.style_elements = 0
        self.inline_styles = 0
        self.links: list[tuple[str, dict[str, str | None], str]] = []
        self.navs: dict[str, list[dict[str, object]]] = {"document-nav": []}
        self.active_nav: dict[str, object] | None = None
        self.ids: list[str] = []
        self.license_text: list[str] = []
        self.license_depth = 0
        self.license_dir = ""
        self.logos: list[dict[str, str | None]] = []
        self.options: list[dict[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if "style" in values:
            self.inline_styles += 1
        if tag == "html":
            self.html_lang = values.get("lang") or ""
            self.html_dir = values.get("dir") or "ltr"
        if tag == "title":
            self.title_depth += 1
        if tag in self.headings:
            self.heading = (tag, len(self.headings[tag]))
            self.headings[tag].append("")
        if tag == "main": self.mains += 1
        if tag == "article": self.articles += 1
        if tag == "style": self.style_elements += 1
        if tag == "link" and "stylesheet" in (values.get("rel") or "").split():
            self.stylesheets.append(values.get("href") or "")
        if tag == "nav" and "document-nav" in (values.get("class") or "").split():
            self.active_nav = {"attrs": values, "links": []}
            self.navs["document-nav"].append(self.active_nav)
        if tag == "a":
            self.links.append((values.get("href") or "", values, ""))
            if self.active_nav:
                self.active_nav["links"].append({"attrs": values, "label": ""})
        if tag == "nav" and self.active_nav and "document-nav" not in (values.get("class") or "").split():
            self.active_nav = None
        if tag == "img" and "brand-logo" in (values.get("class") or "").split(): self.logos.append(values)
        if tag == "option": self.options.append(values)
        if tag == "pre" and "license-text" in (values.get("class") or "").split():
            self.license_depth += 1
            if not self.license_dir: self.license_dir = values.get("dir") or ""
        if values.get("id") is not None: self.ids.append(values["id"] or "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "nav": self.active_nav = None
        if tag == "title" and self.title_depth: self.title_depth -= 1
        if tag == "pre" and self.license_depth: self.license_depth -= 1
        if tag in self.headings: self.heading = None

    def handle_data(self, data: str) -> None:
        if self.title_depth: self.title += data
        if self.heading:
            tag, index = self.heading
            self.headings[tag][index] += data
        if self.license_depth: self.license_text.append(data)


def parse_page(path: Path) -> PageParser:
    parser = PageParser()
    parser.feed(path.read_text(encoding="utf-8"))
    parser.close()
    return parser


def check_local_href(root: Path, href: str) -> str | None:
    parsed = urlsplit(href)
    if parsed.scheme: return None if parsed.scheme in {"mailto", "https", "http"} else f"unsupported link scheme {parsed.scheme}"
    path_part = unquote(parsed.path)
    target = root / path_part if path_part else root / "index.html"
    try: target.resolve().relative_to(root.resolve())
    except ValueError: return f"link escapes site root: {href}"
    if not target.is_file(): return f"broken local link: {href}"
    return None


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    try:
        content = json.loads((root / "content.json").read_text(encoding="utf-8"))
        generated = render_site.expected_files(content, {name: root / "licenses" / name for name in render_site.ASSETS})
    except (OSError, ValueError, KeyError) as error:
        return [f"cannot load generated content: {error}"]
    assets = content.get("source_sha256", {}).get("legal_assets", {})
    for name, expected_hash in assets.items():
        asset = root / "licenses" / name
        if not asset.is_file() or hashlib.sha256(asset.read_bytes()).hexdigest() != expected_hash:
            errors.append(f"license {name} does not match its recorded SHA-256")
    if not (root / "styles.css").is_file(): errors.append("styles.css is missing")
    if not (root / "site.js").is_file(): errors.append("site.js is missing")
    for name in ("gasel-logo.png", "favicon.png"):
        asset = root / name
        if not asset.is_file() or not asset.read_bytes().startswith(PNG_SIGNATURE): errors.append(f"{name} is missing or is not a PNG")

    for locale in content.get("language_order", []):
        language = content["locales"][locale]
        for doc_id in render_site.DOCS:
            filename = render_site.page_name(doc_id, locale)
            path = root / filename
            if not path.is_file():
                errors.append(f"{filename} is missing")
                continue
            try: page = parse_page(path)
            except (OSError, UnicodeError) as error:
                errors.append(f"{filename} cannot be read as UTF-8: {error}")
                continue
            if page.html_lang != language["tag"]: errors.append(f"{filename} has the wrong html lang")
            if page.html_dir != language.get("direction", "ltr"): errors.append(f"{filename} has the wrong html direction")
            if page.stylesheets != ["styles.css"]: errors.append(f"{filename} must use the single shared styles.css")
            if page.style_elements or page.inline_styles: errors.append(f"{filename} contains inline CSS")
            expected = generated[filename]
            if path.read_text(encoding="utf-8") != expected: errors.append(f"{filename} differs from the deterministic template/content render")
            for href, attrs, _ in page.links:
                problem = check_local_href(root, href)
                if problem: errors.append(f"{filename}: {problem}")
                if href.startswith("#") and href[1:] not in page.ids: errors.append(f"{filename} has a missing anchor target: {href}")
            if doc_id == "privacy":
                strings = language["strings"]
                if page.mains != 1 or len(page.headings["h1"]) != 1 or page.headings["h1"][0] != strings["legal_hero_title"]:
                    errors.append(f"{filename} needs one main and the expected hero heading")
                if not {"summary", "privacy", "legal", "open-source"}.issubset(page.ids): errors.append(f"{filename} is missing a page section anchor")
                if len(page.navs["document-nav"]) != 1 or len(page.navs["document-nav"][0]["links"]) != 4:
                    errors.append(f"{filename} must include the four anchored sections in its fixed navigation")
                language_links = [(href, attrs) for href, attrs, _ in page.links if "lang-item" in (attrs.get("class") or "").split()]
                if len(language_links) != len(content["language_order"]): errors.append(f"{filename} language selector does not list every locale")
                elif any(attrs.get("hreflang") != content["locales"][target]["tag"] or href != f'{render_site.page_name("privacy", target)}#summary' for target, (href, attrs) in zip(content["language_order"], language_links)):
                    errors.append(f"{filename} language selector has an incorrect locale link")
                if len(page.logos) != 1 or page.logos[0].get("alt") != "" or page.logos[0].get("width") != "48": errors.append(f"{filename} needs one decorative high-resolution logo beside the Gasel wordmark")
                expected_license = "".join((root / "licenses" / asset).read_text(encoding="utf-8") for asset in render_site.ASSETS)
                if "".join(page.license_text) != expected_license: errors.append(f"{filename} does not contain every complete source license")
                if page.license_dir != "ltr": errors.append(f"{filename} must keep source licenses left-to-right")
            else:
                target = f'{render_site.page_name("privacy", locale)}#{render_site.ANCHORS[doc_id]}'
                if not any(href == target for href, _, _ in page.links): errors.append(f"{filename} must retain a visible link to {target}")

    index = root / "index.html"
    if not index.is_file(): errors.append("index.html is missing")
    elif index.read_text(encoding="utf-8") != generated["index.html"]: errors.append("index.html differs from the deterministic template/content render")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("Legal site validation failed:\n" + "\n".join(f"- {error}" for error in errors))
        return 1
    content = json.loads((ROOT / "content.json").read_text(encoding="utf-8"))
    print(f"Legal site validation passed: {len(content['language_order'])} locales, 141 routes, source licenses and local links.")
    return 0


if __name__ == "__main__": raise SystemExit(main())
