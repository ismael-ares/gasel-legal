#!/usr/bin/env python3
"""Validate all generated legal pages without network access or third-party packages."""

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
        self.stack: list[tuple[str, dict[str, str | None]]] = []
        self.html_lang = ""
        self.title = ""
        self.title_depth = 0
        self.h1: list[str] = []
        self.h2: list[str] = []
        self.heading_depth: tuple[str, int] | None = None
        self.mains = 0
        self.articles = 0
        self.stylesheets: list[str] = []
        self.style_elements = 0
        self.inline_styles = 0
        self.links: list[tuple[str, dict[str, str | None], str]] = []
        self.navs: dict[str, list[dict[str, object]]] = {"document-nav": [], "language-nav": []}
        self.active_nav: tuple[str, dict[str, object]] | None = None
        self.ids: list[str] = []
        self.anchors: list[str] = []
        self.license_text: list[str] = []
        self.license_depth = 0
        self.logos: list[dict[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if "style" in values:
            self.inline_styles += 1
        if tag == "html":
            self.html_lang = values.get("lang") or ""
        if tag == "title":
            self.title_depth += 1
        if tag == "h1":
            self.heading_depth = ("h1", len(self.h1))
            self.h1.append("")
        elif tag == "h2":
            self.heading_depth = ("h2", len(self.h2))
            self.h2.append("")
        if tag == "main":
            self.mains += 1
        if tag == "article":
            self.articles += 1
        if tag == "style":
            self.style_elements += 1
        if tag == "link" and "stylesheet" in (values.get("rel") or "").split():
            self.stylesheets.append(values.get("href") or "")
        if tag == "nav":
            classes = (values.get("class") or "").split()
            for nav_class in self.navs:
                if nav_class in classes:
                    nav_data: dict[str, object] = {"attrs": values, "links": []}
                    self.navs[nav_class].append(nav_data)
                    self.active_nav = (nav_class, nav_data)
                    break
        if tag == "a":
            href = values.get("href") or ""
            self.links.append((href, values, ""))
            self.anchors.append(href)
            if self.active_nav:
                self.active_nav[1]["links"].append({"attrs": values, "label": ""})
        if tag == "img" and "brand-logo" in (values.get("class") or "").split():
            self.logos.append(values)
        if tag == "pre" and "license-text" in (values.get("class") or "").split():
            self.license_depth += 1
        if "id" in values:
            self.ids.append(values["id"] or "")
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append((tag, values))

    def handle_endtag(self, tag: str) -> None:
        if tag == "nav":
            self.active_nav = None
        if tag == "title" and self.title_depth:
            self.title_depth -= 1
        if tag == "pre" and self.license_depth:
            self.license_depth -= 1
        if tag in {"h1", "h2"}:
            self.heading_depth = None
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data: str) -> None:
        if self.title_depth:
            self.title += data
        if self.heading_depth:
            tag, index = self.heading_depth
            if tag == "h1":
                self.h1[index] += data
            else:
                self.h2[index] += data
        if self.active_nav:
            links = self.active_nav[1]["links"]
            if links:
                links[-1]["label"] += data
        if self.license_depth:
            self.license_text.append(data)


def parse_page(path: Path) -> PageParser:
    parser = PageParser()
    parser.feed(path.read_text(encoding="utf-8"))
    parser.close()
    return parser


def check_local_href(root: Path, href: str) -> str | None:
    parsed = urlsplit(href)
    if parsed.scheme:
        return None if parsed.scheme in {"mailto", "https", "http"} else f"unsupported link scheme {parsed.scheme}"
    path_part = unquote(parsed.path)
    if not path_part:
        target = root / "index.html"
    else:
        target = (root / path_part).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        return f"link escapes site root: {href}"
    if not target.is_file():
        return f"broken local link: {href}"
    return None


def validate(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    content_path = root / "content.json"
    license_path = root / "licenses/google-sans-flex.txt"
    if not content_path.is_file():
        return ["content.json is missing"]
    if not license_path.is_file():
        return ["licenses/google-sans-flex.txt is missing"]
    try:
        content = json.loads(content_path.read_text(encoding="utf-8"))
        expected_files = render_site.expected_files(content, license_path)
    except (OSError, ValueError, KeyError) as error:
        return [f"cannot load generated content: {error}"]

    actual_license_hash = hashlib.sha256(license_path.read_bytes()).hexdigest()
    recorded_hash = content.get("source_sha256", {}).get("google_sans_flex_license")
    if actual_license_hash != recorded_hash:
        errors.append("font license does not match its recorded SHA-256")
    if (root / "styles.css").is_file() is False:
        errors.append("styles.css is missing")
    for asset in ("gasel-logo.png", "favicon.png"):
        path = root / asset
        if not path.is_file() or not path.read_bytes().startswith(PNG_SIGNATURE):
            errors.append(f"{asset} is missing or is not a PNG")

    locales = content.get("locales", {})
    document_order = content.get("document_order", [])
    language_order = content.get("language_order", [])
    for locale in language_order:
        language = locales.get(locale)
        if not language:
            errors.append(f"content.json has no locale {locale}")
            continue
        for document_id in document_order:
            filename = render_site.page_name(document_id, locale)
            path = root / filename
            if not path.is_file():
                errors.append(f"{filename} is missing")
                continue
            try:
                page = parse_page(path)
            except (OSError, UnicodeError) as error:
                errors.append(f"{filename} cannot be read as UTF-8: {error}")
                continue
            expected = language["documents"][document_id]
            if page.html_lang != language["tag"]:
                errors.append(f"{filename} has the wrong html lang")
            if not page.title.strip() or len(page.h1) != 1 or page.h1[0].strip() != expected["title"]:
                errors.append(f"{filename} needs a non-empty browser title and the expected single h1")
            if page.mains != 1 or page.articles != 1:
                errors.append(f"{filename} must contain one main and one article")
            if page.h2 != [section["title"] for section in expected["sections"]]:
                errors.append(f"{filename} section headings do not match content.json")
            if page.stylesheets != ["styles.css"]:
                errors.append(f"{filename} must use the single shared styles.css")
            if page.style_elements or page.inline_styles:
                errors.append(f"{filename} contains inline CSS")
            for nav_class in ("document-nav", "language-nav"):
                navs = page.navs[nav_class]
                if len(navs) != 1:
                    errors.append(f"{filename} must have one {nav_class}")
                    continue
                nav = navs[0]
                if not nav["attrs"].get("aria-label"):
                    errors.append(f"{filename} {nav_class} has no accessible name")
                links = nav["links"]
                current = [link for link in links if link["attrs"].get("aria-current") == "page"]
                if len(current) != 1:
                    errors.append(f"{filename} {nav_class} must identify exactly one current page")
                if nav_class == "language-nav":
                    if len(links) != len(language_order):
                        errors.append(f"{filename} language navigation does not list all languages")
                    for target_locale, link in zip(language_order, links):
                        target = locales[target_locale]
                        attrs = link["attrs"]
                        if attrs.get("lang") != target["tag"] or attrs.get("hreflang") != target["tag"]:
                            errors.append(f"{filename} language link {target_locale} lacks matching lang/hreflang")
                        if link["label"].strip() != target["language_name"]:
                            errors.append(f"{filename} language link {target_locale} has no readable native name")
            if len(page.logos) != 1 or page.logos[0].get("alt") != "" or page.logos[0].get("width") != "48":
                errors.append(f"{filename} needs one high-resolution decorative logo beside the Gasel wordmark")
            if len(page.ids) != len(set(page.ids)):
                errors.append(f"{filename} has duplicate ids")
            for href in page.anchors:
                problem = check_local_href(root, href)
                if problem:
                    errors.append(f"{filename}: {problem}")
                elif href.startswith("#") and href[1:] not in page.ids:
                    errors.append(f"{filename} has a missing anchor target: {href}")
            actual_license = "".join(page.license_text)
            if document_id == "licenses":
                if actual_license != license_path.read_text(encoding="utf-8"):
                    errors.append(f"{filename} does not contain the complete source license")
            elif actual_license:
                errors.append(f"{filename} unexpectedly contains a font license block")
            if path.read_text(encoding="utf-8") != expected_files[filename]:
                errors.append(f"{filename} differs from the deterministic template/content render")

    index_path = root / "index.html"
    if not index_path.is_file():
        errors.append("index.html is missing")
    else:
        try:
            index = parse_page(index_path)
            if index.stylesheets != ["styles.css"] or index.mains != 1:
                errors.append("index.html must retain its styled content and shared stylesheet")
            if not any(href == "privacy.html" for href in index.anchors):
                errors.append("index.html must keep a direct privacy-page fallback")
            for href in index.anchors:
                problem = check_local_href(root, href)
                if problem:
                    errors.append(f"index.html: {problem}")
        except (OSError, UnicodeError) as error:
            errors.append(f"index.html cannot be read as UTF-8: {error}")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("Legal site validation failed:\n" + "\n".join(f"- {error}" for error in errors))
        return 1
    pages = len(json.loads((ROOT / "content.json").read_text(encoding="utf-8"))["locales"]) * len(
        json.loads((ROOT / "content.json").read_text(encoding="utf-8"))["document_order"]
    )
    print(f"Legal site validation passed: {pages} localized pages, complete license, local links, and shared assets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
